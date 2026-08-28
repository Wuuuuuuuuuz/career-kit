"""全链路贯通测试——建档 → 差距分析 → 路线图 → 任务执行 → 打卡。

模拟完整用户旅程，验证各工具之间的数据流和状态衔接。
不调用真实 LLM，用模拟响应测试解析和存储链路。
核心理念：顺序归产品，时间归用户——全链路不含任何时长字段。
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
from src.models import CheckIn, CareerProfile
from src.tools.gap_analyzer import format_gap_report
from src.tools.methodology import build_methodology_context
from src.tools.roadmap import format_roadmap, parse_roadmap
from src.tools.task_manager import (
    checkin_task as do_checkin,
    collect_completed_evidence,
    create_tasks_from_roadmap,
    current_phase_view,
    format_progress_overview,
    next_task_id,
)


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

# 任务 schema 为 name/description/priority；无任何时长字段（与 sop/roadmap.yaml 一致）
MOCK_ROADMAP = {
    "roadmap": {
        "strategy_summary": "先补 LangChain 基础，再做 RAG 项目，最后冲刺面试",
        "phases": [
            {
                "id": "phase_1",
                "type": "learn",
                "name": "LangChain 基础",
                "goal": "掌握 LangChain 核心概念和基本用法",
                "kpi": {"metric": "完成官方教程", "target": "100%", "evidence": "能独立写 chain"},
                "resume_value": "",
                "milestones": [
                    {
                        "id": "m1",
                        "name": "LangChain 入门",
                        "tasks": [
                            {"name": "看官方文档 Getting Started", "priority": "high"},
                            {"name": "跑通 quickstart 示例", "priority": "high"},
                            {"name": "学习 Chain/Agent/Tool 概念", "priority": "medium"},
                        ],
                        "deliverable": "能写简单的 chain 和 agent",
                        "done_criteria": "不看文档写出一个 QA chain",
                    },
                    {
                        "id": "m2",
                        "name": "RAG 基础",
                        "tasks": [
                            {"name": "学习向量数据库（Chroma）", "priority": "high"},
                            {"name": "实现简单的文档问答", "priority": "high"},
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
                "goal": "做一个可展示的 RAG 项目",
                "kpi": {"metric": "GitHub star", "target": "50+", "evidence": "项目上线 + star 数"},
                "resume_value": "独立开发 RAG 知识库系统，GitHub 50+ star，支持 PDF/网页/Markdown 多格式文档问答",
                "milestones": [
                    {
                        "id": "m3",
                        "name": "MVP 开发",
                        "tasks": [
                            {"name": "设计项目架构", "priority": "high"},
                            {"name": "实现核心 RAG pipeline", "priority": "high"},
                            {"name": "前端界面开发", "priority": "medium"},
                        ],
                        "deliverable": "可运行的 MVP",
                        "done_criteria": "能处理 PDF 并回答问题",
                    },
                ],
            },
        ],
    }
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


def _build_profile(name: str) -> None:
    """建档：who/have/want。"""
    profile_module.merge_section("who", '{"name":"测试","status":"在职"}', name)
    profile_module.merge_section("have", '{"skills":["Python"],"status":"在职"}', name)
    profile_module.merge_section("want", '{"target_role":"AI Agent 工程师"}', name)


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

        # 填充 have（技能带证据——建档摸排原则）
        p = profile_module.merge_section("have", json.dumps({
            "skills": ["Python", "Django", "FastAPI"],
            "skill_evidence": [{"skill": "FastAPI", "evidence": "电商后端 API", "confidence": "high"}],
            "experience": "2年后端开发",
            "status": "在职",
        }, ensure_ascii=False), name)
        assert "Python" in p.have["skills"]
        assert p.have["skill_evidence"][0]["confidence"] == "high"
        print(f"[OK] have 填充完成: {len(p.have['skills'])} 项技能（含证据）")

        # 填充 want
        p = profile_module.merge_section("want", json.dumps({
            "target_role": "AI Agent 开发工程师",
            "target_companies": ["字节跳动", "阿里巴巴"],
            "salary_expectation": "25-35k",
        }, ensure_ascii=False), name)
        assert p.want["target_role"] == "AI Agent 开发工程师"
        print(f"[OK] want 填充完成: 目标 {p.want['target_role']}")

        # 验证档案完整性 + section 时间戳（目标变更检测的依据）
        p = profile_module.load_profile(name)
        assert p.who and p.have and p.want
        assert set(p.section_updated_at.keys()) >= {"who", "have", "want"}
        print(f"[OK] 档案完整，版本 v{p.version}，section 时间戳已记录")

        print()
        return True
    finally:
        _restore_profile_dir(original_dir)


def test_step2_gap_analysis():
    """步骤2: 差距分析——方法论上下文 + 解析保存。"""
    print("=" * 60)
    print("步骤 2: 差距分析")
    print("=" * 60)

    tmpdir, original_dir, name = _setup_temp_profile()

    try:
        _build_profile(name)
        profile = profile_module.load_profile(name)

        # 构建分析上下文（方法论）
        ctx = build_methodology_context("resume_screening", profile)
        assert ctx["methodology"]
        print("[OK] 差距分析方法论上下文构建成功")

        # 模拟 LLM 已产出结构化结果（解析由 server 层统一 JSON 处理）
        parsed = copy.deepcopy(MOCK_GAP_ANALYSIS)

        # 保存差距分析
        profile.gap = parsed
        profile.touch()
        profile_module.save_profile(profile, name)
        print("[OK] 差距分析已保存到档案")

        # 格式化报告
        report = format_gap_report(parsed)
        assert "55" in report
        assert "LangChain" in report
        print("[OK] 差距报告格式化成功")

        print()
        return True
    finally:
        _restore_profile_dir(original_dir)


def test_step3_roadmap():
    """步骤3: 路线图生成——分阶段计划，无时长字段，任务 schema 统一。"""
    print("=" * 60)
    print("步骤 3: 路线图生成")
    print("=" * 60)

    tmpdir, original_dir, name = _setup_temp_profile()

    try:
        _build_profile(name)
        profile = profile_module.load_profile(name)
        profile.gap = copy.deepcopy(MOCK_GAP_ANALYSIS)
        profile.touch()
        profile_module.save_profile(profile, name)

        # 构建路线图方法论上下文
        ctx = build_methodology_context("roadmap", profile)
        assert ctx["methodology"]
        print("[OK] 路线图方法论上下文构建成功")

        # 解析模拟 LLM 响应（LLM 可能带 code block 包裹）
        mock_response = f"```json\n{json.dumps(MOCK_ROADMAP, ensure_ascii=False)}\n```"
        parsed = parse_roadmap(mock_response)
        roadmap = parsed["roadmap"]
        assert len(roadmap["phases"]) == 2
        assert "total_duration" not in roadmap
        print(f"[OK] 路线图解析成功: {len(roadmap['phases'])} 个阶段，无时长字段")

        # 验证阶段 id 规范化（任务与阶段审计的唯一关联键）
        ids = [p["id"] for p in roadmap["phases"]]
        assert ids == ["phase_1", "phase_2"]
        print(f"[OK] 阶段 id 已规范化: {ids}")

        # 验证任务 schema（name 制）
        for phase in roadmap["phases"]:
            for ms in phase["milestones"]:
                for t in ms["tasks"]:
                    assert t.get("name"), "任务必须有 name 字段"
        print("[OK] 任务 schema 统一为 {name, description, priority}")

        # 验证简历价值
        project_phases = [p for p in roadmap["phases"] if p["type"] != "learn"]
        for p in project_phases:
            assert p.get("resume_value"), f"阶段 {p['name']} 缺少简历价值"
        print("[OK] 非学习阶段都有简历价值")

        # 保存路线图
        profile.plan = parsed
        profile.touch()
        profile_module.save_profile(profile, name)
        print("[OK] 路线图已保存到 plan")

        # 格式化报告
        report = format_roadmap(parsed)
        assert "LangChain" in report
        assert "RAG" in report
        print("[OK] 路线图报告格式化成功")

        print()
        return True
    finally:
        _restore_profile_dir(original_dir)


def test_step4_progress_tracking():
    """步骤4: 进度追踪——任务生成 + 打卡 + 能力证据沉淀。"""
    print("=" * 60)
    print("步骤 4: 进度追踪")
    print("=" * 60)

    tmpdir, original_dir, name = _setup_temp_profile()

    try:
        _build_profile(name)
        profile = profile_module.load_profile(name)
        profile.plan = parse_roadmap(json.dumps(MOCK_ROADMAP, ensure_ascii=False))
        profile.touch()
        profile_module.save_profile(profile, name)
        profile = profile_module.load_profile(name)

        # 从路线图生成任务（无 deadline/estimated_days 概念）
        tasks = create_tasks_from_roadmap(profile)
        assert len(tasks) > 0, "应从路线图生成任务"
        assert all(t.phase_id in ("phase_1", "phase_2") for t in tasks)
        for t in tasks:
            profile.add_task(t)
        profile_module.save_profile(profile, name)
        print(f"[OK] 生成 {len(tasks)} 个任务（阶段 id 与路线图一致）")

        # 打卡第一个任务 → 能力证据沉淀
        first_task_id = tasks[0].id
        profile, saved_checkin = do_checkin(
            profile_module.load_profile(name), first_task_id, "completed", "测试打卡"
        )
        task = profile.get_task(first_task_id)
        from src.tools.task_manager import record_capability_evidence
        record_capability_evidence(profile, task, "测试打卡")
        assert len(profile.checkins) == 1
        evidence = profile.have["capability_evidence"]
        assert len(evidence) == 1 and evidence[0]["task"] == task.name
        completed = [t for t in profile.tasks if t.status == "completed"]
        assert len(completed) == 1
        print(f"[OK] 任务 {first_task_id} 打卡成功，能力证据已沉淀")

        # 当前阶段视图
        view = current_phase_view(profile)
        assert view is not None and view["phase_id"] == "phase_1"
        assert view["total"] > 0 and view["next_tasks"]
        print(f"[OK] 当前阶段视图: {view['phase_name']} ({view['done']}/{view['total']})")

        # 进度概览
        overview = format_progress_overview(profile)
        assert "任务" in overview
        print("[OK] 进度概览格式化成功")

        # ID 递增无冲突
        new_id = next_task_id(profile)
        assert all(new_id != t.id for t in profile.tasks)
        print(f"[OK] 任务 ID 递增无冲突: {new_id}")

        # 持久化后重新加载验证
        profile_module.save_profile(profile, name)
        final = profile_module.load_profile(name)
        assert len(final.checkins) == 1
        assert len(final.tasks) == len(tasks)
        assert len(final.have["capability_evidence"]) == 1
        print("[OK] 打卡与能力证据持久化验证通过")

        print()
        return True
    finally:
        _restore_profile_dir(original_dir)


def test_step5_stage_audit_dedup():
    """步骤5: 阶段审计——完成后触发一次，不重复触发。"""
    print("=" * 60)
    print("步骤 5: 阶段审计去重")
    print("=" * 60)

    tmpdir, original_dir, name = _setup_temp_profile()

    try:
        _build_profile(name)
        profile = profile_module.load_profile(name)
        profile.plan = parse_roadmap(json.dumps(MOCK_ROADMAP, ensure_ascii=False))
        profile.touch()
        profile_module.save_profile(profile, name)
        profile = profile_module.load_profile(name)

        tasks = create_tasks_from_roadmap(profile)
        for t in tasks:
            profile.add_task(t)

        from src.tools.insight import completed_phase_ids

        # 全部完成前：无已完成阶段
        assert completed_phase_ids(profile) == []

        # 完成 phase_1 全部任务
        for t in [x for x in profile.tasks if x.phase_id == "phase_1"]:
            do_checkin(profile, t.id, "completed")
        assert completed_phase_ids(profile) == ["phase_1"]

        # 模拟首次审计登记
        newly = [pid for pid in completed_phase_ids(profile) if pid not in profile.audited_phases]
        profile.audited_phases.extend(newly)
        assert newly == ["phase_1"]

        # 再次检测：不再重复触发
        again = [pid for pid in completed_phase_ids(profile) if pid not in profile.audited_phases]
        assert again == []
        print("[OK] 阶段审计只触发一次，audited_phases 去重生效")

        print()
        return True
    finally:
        _restore_profile_dir(original_dir)


def test_step6_rebuild_preserves_progress():
    """步骤6: 重建任务——历史进度沉淀为能力证据，不丢失。"""
    print("=" * 60)
    print("步骤 6: 重建任务保留进度")
    print("=" * 60)

    tmpdir, original_dir, name = _setup_temp_profile()

    try:
        _build_profile(name)
        profile = profile_module.load_profile(name)
        profile.plan = parse_roadmap(json.dumps(MOCK_ROADMAP, ensure_ascii=False))
        profile.touch()
        profile_module.save_profile(profile, name)
        profile = profile_module.load_profile(name)

        tasks = create_tasks_from_roadmap(profile)
        for t in tasks:
            profile.add_task(t)
        do_checkin(profile, tasks[0].id, "completed", "已看完文档")
        profile_module.save_profile(profile, name)
        profile = profile_module.load_profile(name)

        # 重建前收集证据
        evidence = collect_completed_evidence(profile)
        assert len(evidence) == 1
        assert evidence[0]["notes"] == "已看完文档"

        # 模拟 generate_tasks 的重建逻辑
        have_evidence = profile.have.setdefault("capability_evidence", [])
        have_evidence.extend(evidence)
        profile.tasks = []
        new_tasks = create_tasks_from_roadmap(profile)
        for t in new_tasks:
            profile.add_task(t)
        save_ok = len(new_tasks) == len(tasks)

        profile_module.save_profile(profile, name)
        final = profile_module.load_profile(name)

        assert save_ok
        assert len(final.tasks) == len(tasks)
        assert len(final.checkins) == 1  # 打卡历史仍在
        capability = final.have["capability_evidence"]
        assert any(e.get("task") == tasks[0].name for e in capability if isinstance(e, dict))
        print("[OK] 重建后任务数量一致，历史进度已沉淀为能力证据")

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

        # 写入差距分析 + 路线图
        profile.gap = copy.deepcopy(MOCK_GAP_ANALYSIS)
        profile.plan = parse_roadmap(json.dumps(MOCK_ROADMAP, ensure_ascii=False))
        profile.plan_saved_at = "2026-08-26T10:00:00"
        profile.touch()
        profile_module.save_profile(profile, name)

        # 生成任务并打卡
        profile = profile_module.load_profile(name)
        tasks = create_tasks_from_roadmap(profile)
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
        assert final.plan["roadmap"]["phases"][0]["id"] == "phase_1"
        assert len(final.tasks) == len(tasks)
        assert len(final.checkins) == 1
        print("[OK] 全链路数据连续性验证通过")
        print(f"  - who: {final.who['name']}")
        print(f"  - gap: 匹配度 {final.gap['match_score']}")
        print(f"  - roadmap: {len(final.plan['roadmap']['phases'])} 个阶段")
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

    expected = [
        # 建档
        "start_session", "parse_resume", "intake", "finalize_profile",
        "import_jd", "import_jd_file",
        # 档案管理
        "list_profiles", "switch_profile", "delete_profile",
        # 数据获取与分析
        "list_data_sources", "get_scraper_guide", "fetch_company_jobs",
        "fetch_jd_detail", "search_knowledge",
        "analyze_gaps", "save_gap_analysis",
        # 规划
        "generate_roadmap", "save_roadmap",
        # 任务执行
        "generate_tasks", "get_next_tasks", "checkin_task",
        # 洞察与产出
        "trigger_insight", "apply_insight", "get_progress",
        "get_workflow_status", "export_dashboard",
        # 计划导入
        "import_plan",
    ]

    missing = [t for t in expected if t not in tools]
    extra = [t for t in tools if t not in expected]

    assert not missing, f"缺少工具: {missing}"
    assert not extra, f"多余工具: {extra}"

    for t in sorted(expected):
        print(f"[OK] {t}")
    print(f"\n共注册 {len(tools)} 个 MCP tools")

    print()
    return True


def main():
    """运行全链路测试。"""
    print("\n" + "=" * 60)
    print("全链路贯通测试")
    print("建档 → 差距分析 → 路线图 → 任务执行 → 打卡")
    print("=" * 60 + "\n")

    tests = [
        ("建档", test_step1_build_profile),
        ("差距分析", test_step2_gap_analysis),
        ("路线图", test_step3_roadmap),
        ("进度追踪", test_step4_progress_tracking),
        ("阶段审计去重", test_step5_stage_audit_dedup),
        ("重建保留进度", test_step6_rebuild_preserves_progress),
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
