"""全链路贯通测试——建档 → 差距分析 → 路线图 → 日程 → 进度追踪。

模拟完整用户旅程，验证各工具之间的数据流和状态衔接。
不调用真实 LLM，用模拟响应测试解析和存储链路。
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import src.tools.profile as profile_module
from src.models import CareerProfile
from src.tools.gap_analyzer import format_gap_report, parse_gap_analysis
from src.tools.methodology import build_methodology_context
from src.tools.roadmap import format_roadmap, parse_roadmap
from src.tools.schedule import (
    format_schedule,
    generate_ics,
    parse_schedule,
)
from src.tools.task_manager import (
    checkin_task as do_checkin,
    create_tasks_from_roadmap,
    format_progress_overview,
    set_deadlines,
)
from src.models import CheckIn


# === 模拟 LLM 响应 ===

MOCK_GAP_ANALYSIS = {
    "match_score": 55,
    "match_level": "部分匹配",
    "strengths": [
        {"name": "Python 开发", "detail": "3年经验，熟悉 Django/FastAPI", "resume_tip": "量化 API 性能数据", "interview_tip": "准备性能优化案例"}
    ],
    "resume_optimization": {
        "ats_keywords": ["Python", "AI", "LangChain", "Agent", "RAG"],
        "missing_keywords": ["LangGraph", "向量数据库", "Prompt Engineering"],
        "project_packaging": [
            {"project": "后端 API 项目", "package_as": "AI-ready 后端服务", "quantify": "QPS 提升 200%"}
        ],
        "suggestions": ["补充 AI 相关项目经历", "突出系统设计能力"],
    },
    "interview_preparation": {
        "must_know": [
            {"topic": "LangChain 核心概念", "type": "八股", "prep_time": "3天", "advice": "看官方文档 + 写 demo"}
        ],
        "project_deep_dive": [
            {"project": "后端 API", "likely_questions": ["如何做限流"], "key_points": ["令牌桶算法"], "star_story": "S:流量突增 QPS 翻倍"}
        ],
        "system_design": [
            {"topic": "设计 RAG 系统", "framework": "需求→架构→组件→优化"}
        ],
        "behavioral": [
            {"question": "遇到过什么技术难题", "story_template": "用后端性能优化的故事"}
        ],
        "study_plan": {
            "week_1": ["LangChain 基础", "看文档", "跑 demo"],
            "week_2": ["RAG 实战", "实现 PDF QA"],
        },
    },
    "skill_gaps": [
        {"skill": "LangChain", "current_level": "不了解", "required_level": "熟练", "priority": "high", "is_hidden": False, "how_to_improve": "看官方文档 + 做项目"},
        {"skill": "系统设计", "current_level": "初级", "required_level": "能独立设计", "priority": "high", "is_hidden": True, "how_to_improve": "多做系统设计题"},
    ],
    "priority_actions": [
        {"action": "学习 LangChain", "timeline": "2周", "impact": "high", "difficulty": "medium"}
    ],
    "market_context": "AI Agent 岗位需求增长 150%",
}

MOCK_ROADMAP = {
    "roadmap": {
        "total_duration": "2个月",
        "strategy_summary": "先补 LangChain 基础，再做 RAG 项目，最后冲刺面试",
        "phases": [
            {
                "id": "phase_1",
                "type": "learn",
                "name": "LangChain 基础",
                "duration": "第1-3周",
                "goal": "掌握 LangChain 核心概念和基本用法",
                "kpi": {"metric": "完成官方教程", "target": "100%", "evidence": "能独立写 chain"},
                "resume_value": "",
                "milestones": [
                    {
                        "id": "m1",
                        "name": "LangChain 入门",
                        "duration": "第1-2周",
                        "tasks": [
                            {"task": "看官方文档 Getting Started", "time": "3天", "priority": "high"},
                            {"task": "跑通 quickstart 示例", "time": "1天", "priority": "high"},
                            {"task": "学习 Chain/Agent/Tool 概念", "time": "3天", "priority": "medium"},
                        ],
                        "deliverable": "能写简单的 chain 和 agent",
                        "done_criteria": "不看文档写出一个 QA chain",
                    },
                    {
                        "id": "m2",
                        "name": "RAG 基础",
                        "duration": "第3周",
                        "tasks": [
                            {"task": "学习向量数据库（Chroma）", "time": "2天", "priority": "high"},
                            {"task": "实现简单的文档问答", "time": "3天", "priority": "high"},
                        ],
                        "deliverable": "能对 PDF 做问答",
                        "done_criteria": "上传 PDF 后能回答相关问题",
                    },
                ],
            },
            {
                "id": "phase_2",
                "type": "project",
                "name": "RAG 项目实战",
                "duration": "第4-6周",
                "goal": "做一个可展示的 RAG 项目",
                "kpi": {"metric": "GitHub star", "target": "50+", "evidence": "项目上线 + star 数"},
                "resume_value": "独立开发 RAG 知识库系统，GitHub 50+ star，支持 PDF/网页/Markdown 多格式文档问答",
                "milestones": [
                    {
                        "id": "m3",
                        "name": "MVP 开发",
                        "duration": "第4-5周",
                        "tasks": [
                            {"task": "设计项目架构", "time": "2天", "priority": "high"},
                            {"task": "实现核心 RAG pipeline", "time": "5天", "priority": "high"},
                            {"task": "前端界面开发", "time": "3天", "priority": "medium"},
                        ],
                        "deliverable": "可运行的 MVP",
                        "done_criteria": "能处理 PDF 并回答问题",
                    },
                    {
                        "id": "m4",
                        "name": "优化上线",
                        "duration": "第6周",
                        "tasks": [
                            {"task": "性能优化（检索精度）", "time": "3天", "priority": "high"},
                            {"task": "部署上线 + README", "time": "2天", "priority": "high"},
                        ],
                        "deliverable": "线上可访问的项目",
                        "done_criteria": "有完整文档和 demo",
                    },
                ],
            },
            {
                "id": "phase_3",
                "type": "learn",
                "name": "面试冲刺",
                "duration": "第7-8周",
                "goal": "刷题 + 模拟面试",
                "kpi": {"metric": "LeetCode 刷题", "target": "50道", "evidence": "提交记录"},
                "resume_value": "",
                "milestones": [
                    {
                        "id": "m5",
                        "name": "算法刷题",
                        "duration": "第7-8周",
                        "tasks": [
                            {"task": "每天刷 2-3 道 LeetCode", "time": "每天2小时", "priority": "high"},
                            {"task": "整理高频面试题", "time": "3天", "priority": "medium"},
                        ],
                        "deliverable": "50 道 LeetCode",
                        "done_criteria": "中等难度能在30分钟内AC",
                    },
                ],
            },
        ],
    }
}

MOCK_SCHEDULE = {
    "schedule": {
        "total_days": 5,
        "daily_plans": [
            {
                "day": 1,
                "date": "Day 1",
                "theme": "LangChain 入门",
                "blocks": [
                    {"time": "09:00-11:00", "task": "看 LangChain 官方文档 Getting Started", "type": "learn", "priority": "high"},
                    {"time": "11:15-12:15", "task": "跑通 quickstart 示例", "type": "practice", "priority": "high"},
                    {"time": "14:00-15:30", "task": "阅读 Chain 源码", "type": "learn", "priority": "medium"},
                ],
                "total_hours": 4.5,
                "notes": "重点理解 Chain 的概念",
            },
            {
                "day": 2,
                "date": "Day 2",
                "theme": "Agent 与 Tool",
                "blocks": [
                    {"time": "09:00-11:00", "task": "学习 Agent 概念", "type": "learn", "priority": "high"},
                    {"time": "11:15-12:15", "task": "实现一个自定义 Tool", "type": "practice", "priority": "high"},
                    {"time": "14:00-16:00", "task": "完成 Agent + Tool 联动示例", "type": "practice", "priority": "medium"},
                ],
                "total_hours": 5,
            },
            {
                "day": 3,
                "date": "Day 3",
                "theme": "向量数据库",
                "blocks": [
                    {"time": "09:00-10:30", "task": "学习 Chroma 基础", "type": "learn", "priority": "high"},
                    {"time": "10:45-12:00", "task": "实现文档 embedding + 检索", "type": "practice", "priority": "high"},
                ],
                "total_hours": 3,
            },
            {
                "day": 4,
                "date": "Day 4",
                "theme": "复习日",
                "blocks": [
                    {"time": "09:00-10:30", "task": "回顾 Day 1-3 内容", "type": "review", "priority": "medium"},
                    {"time": "10:45-12:00", "task": "整理笔记，查漏补缺", "type": "review", "priority": "medium"},
                ],
                "total_hours": 3,
                "notes": "间隔复习，巩固记忆",
            },
            {
                "day": 5,
                "date": "Day 5",
                "theme": "RAG 实战",
                "blocks": [
                    {"time": "09:00-12:00", "task": "实现简单的 PDF 问答系统", "type": "project", "priority": "high"},
                    {"time": "14:00-16:00", "task": "测试不同文档格式", "type": "practice", "priority": "medium"},
                ],
                "total_hours": 5,
            },
        ],
    }
}

MOCK_CHECKIN_1 = {
    "completed_tasks": ["看 LangChain 官方文档", "跑通 quickstart", "阅读 Chain 源码"],
    "progress_pct": 15,
    "time_spent": "4.5小时",
    "blockers": [],
    "morale": "high",
    "deviation": {"on_track": True, "days_ahead_or_behind": 0, "reason": "进度正常"},
    "next_steps": ["继续学习 Agent 概念"],
    "adjustments": {"needed": False},
}

MOCK_CHECKIN_2 = {
    "completed_tasks": ["学习 Agent 概念", "实现自定义 Tool", "Agent + Tool 联动"],
    "progress_pct": 30,
    "time_spent": "5小时",
    "blockers": ["Tool 调用偶尔超时"],
    "morale": "neutral",
    "deviation": {"on_track": True, "days_ahead_or_behind": 0, "reason": "按计划推进"},
    "next_steps": ["学习向量数据库"],
    "adjustments": {"needed": False},
}

MOCK_CHECKIN_3_LAGGING = {
    "completed_tasks": ["学习 Chroma 基础"],
    "progress_pct": 35,
    "time_spent": "1.5小时",
    "blockers": ["embedding 模型加载失败", "网络问题导致下载超时"],
    "morale": "low",
    "deviation": {"on_track": False, "days_ahead_or_behind": -1, "reason": "环境问题导致落后一天"},
    "next_steps": ["解决环境问题", "补上落后的进度"],
    "adjustments": {
        "needed": True,
        "reason": "环境问题导致落后",
        "suggested_changes": ["将 Day 4 复习日改为补进度日", "压缩 Day 5 内容"],
    },
}


_test_counter = 0


def _setup_temp_profile():
    """设置临时 profile 目录，使用唯一 profile name 避免跨测试污染。"""
    global _test_counter
    _test_counter += 1
    tmpdir = Path(tempfile.mkdtemp())
    original_dir = profile_module.PROFILE_DIR
    profile_module.PROFILE_DIR = tmpdir
    profile_name = f"test_{_test_counter}"
    return tmpdir, original_dir, profile_name


def _restore_profile_dir(original_dir):
    """恢复原始 profile 目录。"""
    profile_module.PROFILE_DIR = original_dir


# === 测试函数 ===


def test_step1_build_profile():
    """步骤1: 建档——模拟用户输入 who/have/want。"""
    print("=" * 60)
    print("步骤 1: 建档")
    print("=" * 60)

    tmpdir, original_dir, name = _setup_temp_profile()

    try:
        # 填充 who
        p = profile_module.merge_section("who", json.dumps({
            "name": "测试用户",
            "status": "在职，2年后端经验",
            "education": "本科 计算机科学",
        }, ensure_ascii=False), name)
        assert p.who["name"] == "测试用户"
        print(f"[OK] who 填充完成: {p.who['name']}")

        # 填充 have
        p = profile_module.merge_section("have", json.dumps({
            "skills": ["Python", "Django", "FastAPI", "PostgreSQL", "Docker"],
            "experience": "2年后端开发",
            "projects": ["电商后端 API", "数据采集平台"],
            "status": "在职",
        }, ensure_ascii=False), name)
        assert "Python" in p.have["skills"]
        print(f"[OK] have 填充完成: {len(p.have['skills'])} 项技能")

        # 填充 want
        p = profile_module.merge_section("want", json.dumps({
            "target_role": "AI Agent 开发工程师",
            "target_companies": ["字节跳动", "阿里巴巴", "蚂蚁集团"],
            "timeline": "3个月",
            "salary_expectation": "25-35k",
        }, ensure_ascii=False), name)
        assert p.want["target_role"] == "AI Agent 开发工程师"
        print(f"[OK] want 填充完成: 目标 {p.want['target_role']}")

        # 验证档案完整性
        p = profile_module.load_profile(name)
        assert p.who and p.have and p.want
        assert p.version == 3
        print(f"[OK] 档案完整，版本 v{p.version}")

        print()
        return True
    finally:
        _restore_profile_dir(original_dir)


def test_step2_gap_analysis():
    """步骤2: 差距分析——构建 prompt + 解析模拟 LLM 响应。"""
    print("=" * 60)
    print("步骤 2: 差距分析")
    print("=" * 60)

    tmpdir, original_dir, name = _setup_temp_profile()

    try:
        # 先建档
        profile_module.merge_section("who", '{"name":"测试","status":"在职","education":"本科"}', name)
        profile_module.merge_section("have", '{"skills":["Python","Django"],"status":"在职"}', name)
        profile_module.merge_section("want", '{"target_role":"AI Agent 工程师","timeline":"3个月"}', name)

        profile = profile_module.load_profile(name)

        # 构建分析上下文（方法论）
        ctx = build_methodology_context("resume_screening", profile)
        assert ctx["methodology"]
        print(f"[OK] 差距分析方法论上下文构建成功")

        # 模拟 LLM 响应解析
        mock_response = f"```json\n{json.dumps(MOCK_GAP_ANALYSIS, ensure_ascii=False)}\n```"
        parsed = parse_gap_analysis(mock_response)
        assert parsed["match_score"] == 55
        assert len(parsed["strengths"]) > 0
        print(f"[OK] 差距分析解析成功: 匹配度 {parsed['match_score']}")

        # 保存差距分析
        profile.gap = parsed
        profile.touch()
        profile_module.save_profile(profile, name)
        print(f"[OK] 差距分析已保存到档案")

        # 格式化报告
        report = format_gap_report(parsed)
        assert "55" in report
        assert "LangChain" in report
        print(f"[OK] 差距报告格式化成功")

        print()
        return True
    finally:
        _restore_profile_dir(original_dir)


def test_step3_roadmap():
    """步骤3: 路线图生成——基于差距分析生成分阶段计划。"""
    print("=" * 60)
    print("步骤 3: 路线图生成")
    print("=" * 60)

    tmpdir, original_dir, name = _setup_temp_profile()

    try:
        # 建档 + 差距分析
        profile_module.merge_section("who", '{"name":"测试","status":"在职"}', name)
        profile_module.merge_section("have", '{"skills":["Python"],"status":"在职"}', name)
        profile_module.merge_section("want", '{"target_role":"AI Agent 工程师"}', name)

        profile = profile_module.load_profile(name)
        profile.gap = copy.deepcopy(MOCK_GAP_ANALYSIS)
        profile.touch()
        profile_module.save_profile(profile, name)

        # 构建路线图方法论上下文
        ctx = build_methodology_context("roadmap", profile)
        assert ctx["methodology"]
        print(f"[OK] 路线图方法论上下文构建成功")

        # 解析模拟 LLM 响应
        mock_response = f"```json\n{json.dumps(MOCK_ROADMAP, ensure_ascii=False)}\n```"
        parsed = parse_roadmap(mock_response)
        roadmap = parsed["roadmap"]
        assert roadmap["total_duration"] == "2个月"
        assert len(roadmap["phases"]) == 3
        print(f"[OK] 路线图解析成功: {len(roadmap['phases'])} 个阶段")

        # 验证阶段类型
        phase_types = [p["type"] for p in roadmap["phases"]]
        assert "learn" in phase_types
        assert "project" in phase_types
        print(f"[OK] 阶段类型: {phase_types}")

        # 验证 KPI
        for phase in roadmap["phases"]:
            assert "kpi" in phase
            assert phase["kpi"]["target"]
        print(f"[OK] 每个阶段都有量化 KPI")

        # 验证简历价值
        project_phases = [p for p in roadmap["phases"] if p["type"] != "learn"]
        for p in project_phases:
            assert p.get("resume_value"), f"阶段 {p['name']} 缺少简历价值"
        print(f"[OK] 非学习阶段都有简历价值")

        # 保存路线图
        profile.plan = parsed
        profile.touch()
        profile_module.save_profile(profile, name)
        print(f"[OK] 路线图已保存到 plan")

        # 格式化报告
        report = format_roadmap(parsed)
        assert "LangChain" in report
        assert "RAG" in report
        print(f"[OK] 路线图报告格式化成功")

        print()
        return True
    finally:
        _restore_profile_dir(original_dir)


def test_step4_schedule():
    """步骤4: 日程生成——将路线图拆解为每日时间块。"""
    print("=" * 60)
    print("步骤 4: 日程生成")
    print("=" * 60)

    tmpdir, original_dir, name = _setup_temp_profile()

    try:
        # 建档 + 差距分析 + 路线图
        profile_module.merge_section("who", '{"name":"测试","status":"在职"}', name)
        profile_module.merge_section("have", '{"skills":["Python"],"status":"在职"}', name)
        profile_module.merge_section("want", '{"target_role":"AI Agent 工程师"}', name)

        profile = profile_module.load_profile(name)
        profile.gap = copy.deepcopy(MOCK_GAP_ANALYSIS)
        profile.plan = copy.deepcopy(MOCK_ROADMAP)
        profile.touch()
        profile_module.save_profile(profile, name)

        # 构建日程方法论上下文
        ctx = build_methodology_context("schedule", profile)
        assert ctx["methodology"]
        print(f"[OK] 日程方法论上下文构建成功")

        # 解析模拟 LLM 响应
        mock_response = f"```json\n{json.dumps(MOCK_SCHEDULE, ensure_ascii=False)}\n```"
        parsed = parse_schedule(mock_response)
        schedule = parsed["schedule"]
        assert schedule["total_days"] == 5
        assert len(schedule["daily_plans"]) == 5
        print(f"[OK] 日程解析成功: {schedule['total_days']} 天")

        # 验证时间块
        total_blocks = sum(len(d["blocks"]) for d in schedule["daily_plans"])
        assert total_blocks > 0
        print(f"[OK] 共 {total_blocks} 个时间块")

        # 验证复习日
        review_days = [d for d in schedule["daily_plans"] if any(b["type"] == "review" for b in d["blocks"])]
        assert len(review_days) > 0
        print(f"[OK] 包含 {len(review_days)} 个复习日")

        # 保存日程
        profile.plan["schedule"] = schedule
        profile.touch()
        profile_module.save_profile(profile, name)
        print(f"[OK] 日程已保存到 plan")

        # 格式化报告
        report = format_schedule(parsed)
        assert "LangChain" in report
        assert "复习" in report
        print(f"[OK] 日程报告格式化成功")

        # 生成 ICS
        ics = generate_ics(parsed, "2026-08-25")
        assert "BEGIN:VCALENDAR" in ics
        assert "END:VCALENDAR" in ics
        assert "20260825" in ics
        print(f"[OK] ICS 日历文件生成成功")

        print()
        return True
    finally:
        _restore_profile_dir(original_dir)


def test_step5_progress_tracking():
    """步骤5: 进度追踪——任务生成 + 打卡 + 进度概览（任务级系统）。"""
    print("=" * 60)
    print("步骤 5: 进度追踪")
    print("=" * 60)

    tmpdir, original_dir, name = _setup_temp_profile()

    try:
        # 建档 + 路线图
        profile_module.merge_section("who", '{"name":"测试","status":"在职"}', name)
        profile = profile_module.load_profile(name)
        profile.plan = copy.deepcopy(MOCK_ROADMAP)
        profile.touch()
        profile_module.save_profile(profile, name)
        profile = profile_module.load_profile(name)

        # 从路线图生成任务
        tasks = create_tasks_from_roadmap(profile)
        assert len(tasks) > 0, "应从路线图生成任务"
        tasks = set_deadlines(tasks)
        for t in tasks:
            profile.add_task(t)
        profile_module.save_profile(profile, name)
        print(f"[OK] 生成 {len(tasks)} 个任务")

        # 打卡第一个任务
        first_task_id = tasks[0].id
        checkin = CheckIn(task_id=first_task_id, status="completed", notes="测试打卡")
        profile, saved_checkin = do_checkin(
            profile_module.load_profile(name), first_task_id, "completed", "测试打卡"
        )
        assert len(profile.checkins) == 1
        completed = [t for t in profile.tasks if t.status == "completed"]
        assert len(completed) == 1
        print(f"[OK] 任务 {first_task_id} 打卡成功")

        # 进度概览
        overview = format_progress_overview(profile)
        assert "任务" in overview
        print(f"[OK] 进度概览格式化成功")

        # 持久化后重新加载验证
        profile_module.save_profile(profile, name)
        final = profile_module.load_profile(name)
        assert len(final.checkins) == 1
        assert len(final.tasks) == len(tasks)
        print(f"[OK] 打卡数据持久化验证通过")

        print()
        return True
    finally:
        _restore_profile_dir(original_dir)


def test_step7_data_continuity():
    """步骤7: 数据连续性——验证从建档到任务打卡的完整数据流。"""
    print("=" * 60)
    print("步骤 7: 数据连续性验证")
    print("=" * 60)

    tmpdir, original_dir, name = _setup_temp_profile()

    try:
        # 模拟完整流程
        profile_module.merge_section("who", '{"name":"连续性测试"}', name)
        profile_module.merge_section("have", '{"skills":["Python"]}', name)
        profile_module.merge_section("want", '{"target_role":"AI Engineer"}', name)

        profile = profile_module.load_profile(name)

        # 写入差距分析
        profile.gap = copy.deepcopy(MOCK_GAP_ANALYSIS)
        profile.touch()
        profile_module.save_profile(profile, name)

        # 写入路线图 + 日程
        profile.plan = copy.deepcopy(MOCK_ROADMAP)
        profile.plan["schedule"] = copy.deepcopy(MOCK_SCHEDULE["schedule"])
        profile.touch()
        profile_module.save_profile(profile, name)

        # 生成任务并打卡
        profile = profile_module.load_profile(name)
        tasks = create_tasks_from_roadmap(profile)
        tasks = set_deadlines(tasks)
        for t in tasks:
            profile.add_task(t)
        profile, _ = do_checkin(profile, tasks[0].id, "completed")
        profile_module.save_profile(profile, name)

        # 重新加载，验证所有数据都在
        final = profile_module.load_profile(name)
        assert final.who["name"] == "连续性测试"
        assert "skills" in final.have
        assert final.want["target_role"] == "AI Engineer"
        assert final.gap["match_score"] == 55
        assert final.plan["roadmap"]["total_duration"] == "2个月"
        assert final.plan["schedule"]["total_days"] == 5
        assert len(final.tasks) == len(tasks)
        assert len(final.checkins) == 1
        print(f"[OK] 全链路数据连续性验证通过")
        print(f"  - who: {final.who['name']}")
        print(f"  - gap: 匹配度 {final.gap['match_score']}")
        print(f"  - roadmap: {final.plan['roadmap']['total_duration']}")
        print(f"  - schedule: {final.plan['schedule']['total_days']} 天")
        print(f"  - tasks: {len(final.tasks)} 个，checkins: {len(final.checkins)} 次")

        print()
        return True
    finally:
        _restore_profile_dir(original_dir)


def test_step8_mcp_tools_registered():
    """步骤8: 验证所有 MCP tools 已注册。"""
    print("=" * 60)
    print("步骤 8: MCP Tools 注册验证")
    print("=" * 60)

    from src.server import mcp

    tools = {t.name for t in mcp._tool_manager.list_tools()}

    # 全链路工具
    chain_tools = [
        "start_session",
        "parse_resume", "intake", "finalize_profile",
        "import_jd", "import_jd_file", "analyze_gaps", "save_gap_analysis",
        "generate_roadmap", "save_roadmap",
        "generate_schedule", "save_schedule", "export_ics",
        "search_knowledge",
    ]

    # 任务与洞察工具
    task_tools = [
        "generate_tasks", "get_today_tasks", "checkin_task",
        "trigger_insight", "apply_insight", "get_progress", "suggest_adjustment",
        "get_workflow_status",
    ]

    # 版本管理工具
    version_tools = [
        "import_plan", "compare_plan_versions", "replace_plan",
        "merge_plan", "list_plan_versions", "restore_plan",
    ]

    all_expected = chain_tools + task_tools + version_tools
    missing = [t for t in all_expected if t not in tools]

    if missing:
        print(f"[FAIL] 缺少工具: {missing}")
        return False

    for t in all_expected:
        print(f"[OK] {t}")

    print(f"\n共注册 {len(tools)} 个 MCP tools")
    print()
    return True


def main():
    """运行全链路测试。"""
    print("\n" + "=" * 60)
    print("全链路贯通测试")
    print("建档 → 差距分析 → 路线图 → 日程 → 进度追踪")
    print("=" * 60 + "\n")

    tests = [
        ("建档", test_step1_build_profile),
        ("差距分析", test_step2_gap_analysis),
        ("路线图", test_step3_roadmap),
        ("日程生成", test_step4_schedule),
        ("进度追踪", test_step5_progress_tracking),
        ("数据连续性", test_step7_data_continuity),
        ("MCP Tools", test_step8_mcp_tools_registered),
    ]

    passed = 0
    failed = 0

    for name, test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"[FAIL] {name}: 返回 False")
        except Exception as e:
            failed += 1
            print(f"[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            print()

    print("=" * 60)
    print(f"全链路测试结果: {passed} 通过, {failed} 失败")
    if failed == 0:
        print("全链路贯通成功！")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
