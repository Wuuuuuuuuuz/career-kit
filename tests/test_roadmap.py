"""路线图功能测试。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8')

from src.models import CareerProfile
from src.tools.roadmap import (
    format_roadmap,
    parse_roadmap,
)
from src.tools.methodology import load_methodology


def test_sop_config():
    """测试路线图方法论配置加载。"""
    print("=" * 60)
    print("测试 1: 路线图方法论配置")
    print("=" * 60)

    m = load_methodology("roadmap")
    assert m["name"] == "路线图生成"
    phase_ids = [p["id"] for p in m["methodology"]["phases"]]
    assert "gather_market_data" in phase_ids
    assert "design_roadmap" in phase_ids
    print(f"[OK] 路线图方法论加载成功，{len(phase_ids)} 阶段")

    print()


def test_parse_roadmap():
    """测试路线图解析：name 制任务 schema，无时长字段，阶段 id 规范化。"""
    print("=" * 60)
    print("测试 2: 解析路线图 JSON")
    print("=" * 60)

    llm_response = '''
    ```json
    {
        "roadmap": {
            "total_duration": "3个月",
            "strategy_summary": "先补基础再做项目再实习",
            "phases": [
                {
                    "id": "phase_1",
                    "type": "learn",
                    "name": "AI Agent 基础补齐",
                    "duration": "第1-4周",
                    "goal": "掌握 LangChain + RAG 核心技能",
                    "kpi": {
                        "metric": "LeetCode 刷题",
                        "target": "100道",
                        "evidence": "LeetCode 提交记录"
                    },
                    "resume_value": "",
                    "milestones": [
                        {
                            "id": "m1",
                            "name": "LangChain 基础",
                            "duration": "第1-2周",
                            "tasks": [
                                {"name": "看官方文档", "priority": "high"},
                                {"name": "跑通 quickstart", "priority": "high"}
                            ],
                            "deliverable": "能独立写简单 Agent",
                            "done_criteria": "不看文档写出来"
                        }
                    ]
                },
                {
                    "type": "project",
                    "name": "RAG 项目实战",
                    "goal": "做一个可展示的 RAG 项目",
                    "kpi": {
                        "metric": "GitHub star",
                        "target": "50+",
                        "evidence": "GitHub 仓库 star 数"
                    },
                    "resume_value": "独立开发 RAG 系统，支持 10 种文档格式，GitHub 50+ star",
                    "milestones": [
                        {
                            "name": "MVP 开发",
                            "tasks": [
                                {"name": "设计架构", "description": "确定技术栈与数据流", "priority": "high"},
                                {"name": "实现核心功能", "priority": "high"}
                            ],
                            "deliverable": "可运行的 MVP",
                            "done_criteria": "能处理 PDF 文档"
                        }
                    ]
                }
            ]
        }
    }
    ```
    '''

    result = parse_roadmap(llm_response)
    roadmap = result["roadmap"]

    # 产品不规划时间：时长字段被剥离
    assert "total_duration" not in roadmap
    assert len(roadmap["phases"]) == 2

    # 阶段 id 由解析器规范化（即使 LLM 没给）
    assert roadmap["phases"][0]["id"] == "phase_1"
    assert roadmap["phases"][1]["id"] == "phase_2"

    # 任务 schema 统一为 {name, description, priority}
    for phase in roadmap["phases"]:
        for ms in phase["milestones"]:
            for t in ms["tasks"]:
                assert t.get("name"), f"任务缺少 name: {t}"
                assert "task" not in t or t["name"], "旧 task 字段不应被依赖"

    assert roadmap["phases"][0]["type"] == "learn"
    assert roadmap["phases"][1]["type"] == "project"
    assert roadmap["phases"][1]["resume_value"] != ""
    assert roadmap["phases"][0]["kpi"]["target"] == "100道"
    print("[OK] 标准路线图解析成功（无时长字段，id 规范化，name 制 schema）")

    # 测试解析失败
    result2 = parse_roadmap("这不是 JSON")
    assert "raw_roadmap" in result2
    print("[OK] 解析失败返回原始文本")

    print()


def test_format_roadmap():
    """测试路线图格式化（无时长字段版本）。"""
    print("=" * 60)
    print("测试 3: 格式化路线图")
    print("=" * 60)

    roadmap_data = {
        "roadmap": {
            "strategy_summary": "先补基础再做项目",
            "phases": [
                {
                    "id": "phase_1",
                    "type": "learn",
                    "name": "基础补齐",
                    "goal": "掌握核心技能",
                    "kpi": {
                        "metric": "LeetCode 刷题",
                        "target": "100道",
                        "evidence": "提交记录"
                    },
                    "resume_value": "",
                    "milestones": [
                        {
                            "id": "m1",
                            "name": "LangChain 基础",
                            "tasks": [
                                {"name": "看官方文档", "priority": "high"},
                                {"name": "跑通 quickstart", "priority": "medium"},
                            ],
                            "deliverable": "能写简单 Agent",
                            "done_criteria": "不看文档写出来",
                        }
                    ],
                },
                {
                    "id": "phase_2",
                    "type": "project",
                    "name": "项目实战",
                    "goal": "做出可展示的项目",
                    "kpi": {
                        "metric": "GitHub star",
                        "target": "50+",
                        "evidence": "star 数"
                    },
                    "resume_value": "独立开发 RAG 系统，GitHub 50+ star",
                    "milestones": [
                        {
                            "id": "m1",
                            "name": "MVP",
                            "tasks": [
                                {"name": "设计架构", "priority": "high"},
                            ],
                            "deliverable": "可运行 MVP",
                            "done_criteria": "能处理 PDF",
                        }
                    ],
                },
            ],
        }
    }

    report = format_roadmap(roadmap_data)

    assert "基础补齐" in report
    assert "learn" in report
    assert "project" in report
    assert "LeetCode" in report
    assert "简历价值" in report
    assert "LangChain" in report
    assert "[高]" in report or "[中]" in report or "[低]" in report
    assert "交付物" in report
    assert "完成标准" in report
    print("[OK] 路线图格式化成功")

    print(f"\n报告预览:\n{'-' * 40}")
    print(report[:1200])
    print(f"{'-' * 40}\n")


def test_build_roadmap_context():
    """测试路线图方法论上下文构建。"""
    print("=" * 60)
    print("测试 4: 路线图方法论上下文构建")
    print("=" * 60)

    profile = CareerProfile()
    profile.have = {"skills": ["Python", "React"], "experience": "2年前端"}
    profile.want = {"target_role": "AI Agent 开发工程师", "timeline": "3个月"}
    profile.gap = {
        "match_score": 45,
        "match_level": "partial_match",
        "skill_gaps": [
            {"skill": "LangGraph", "current_level": "不了解", "required_level": "熟练", "priority": "high", "how_to_improve": "学官方文档"},
            {"skill": "RAG", "current_level": "了解", "required_level": "熟练", "priority": "medium"},
        ],
        "priority_actions": [
            {"action": "学习 LangGraph", "timeline": "2个月", "impact": "高", "difficulty": "medium"},
        ],
        "resume_optimization": {
            "missing_experiences": [
                {"experience": "AI Agent 开发经验", "how_to_create": "做一个 RAG 项目"},
            ],
        },
    }

    from src.tools.methodology import build_methodology_context

    ctx = build_methodology_context("roadmap", profile)

    assert ctx["methodology"]
    assert "profile" in ctx
    prompt = json.dumps(ctx, ensure_ascii=False, default=str)
    assert "LangGraph" in prompt or "roadmap" in prompt.lower()
    print("[OK] 方法论上下文构建成功")

    print()


def test_mcp_tools():
    """测试 MCP tools 注册。"""
    print("=" * 60)
    print("测试 5: MCP Tools 注册")
    print("=" * 60)

    from src.server import mcp

    tools = [t.name for t in mcp._tool_manager.list_tools()]

    assert "generate_roadmap" in tools
    assert "save_roadmap" in tools
    print("[OK] generate_roadmap 已注册")
    print("[OK] save_roadmap 已注册")

    print()


def main():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("路线图功能测试套件")
    print("=" * 60 + "\n")

    tests = [
        test_sop_config,
        test_parse_roadmap,
        test_format_roadmap,
        test_build_roadmap_context,
        test_mcp_tools,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            print()

    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
