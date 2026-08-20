"""日程生成 + 进度追踪 + 市场搜索测试。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8')

from src.models import CareerProfile
from src.tools.schedule import (
    build_schedule_prompt,
    format_schedule,
    generate_ics,
    parse_schedule,
)
from src.tools.progress import (
    build_checkin_prompt,
    format_checkin_report,
    format_progress_overview,
    parse_checkin_response,
    save_checkin,
)
from src.tools.market import search_market_data, build_market_search_prompt


# === 日程生成测试 ===

def test_schedule_sop_config():
    """测试日程 SOP 配置。"""
    print("=" * 60)
    print("测试 1: 日程 SOP 配置")
    print("=" * 60)

    from src.tools.sop_executor import load_sop
    sop = load_sop("schedule")
    assert sop["name"] == "日程生成"
    assert len(sop["steps"]) == 2
    print(f"[OK] 日程 SOP 加载成功，{len(sop['steps'])} 步")
    print()


def test_parse_schedule():
    """测试日程解析。"""
    print("=" * 60)
    print("测试 2: 解析日程 JSON")
    print("=" * 60)

    llm_response = '''
    ```json
    {
        "schedule": {
            "total_days": 3,
            "daily_plans": [
                {
                    "day": 1,
                    "date": "Day 1",
                    "theme": "LangChain 基础",
                    "blocks": [
                        {"time": "09:00-11:00", "task": "看官方文档", "type": "learn", "priority": "high"},
                        {"time": "11:15-12:15", "task": "跑 quickstart", "type": "practice", "priority": "high"}
                    ],
                    "total_hours": 3,
                    "notes": "重点理解 chain 的概念"
                },
                {
                    "day": 2,
                    "date": "Day 2",
                    "theme": "LangChain 实战",
                    "blocks": [
                        {"time": "09:00-11:00", "task": "完成示例项目", "type": "practice", "priority": "medium"}
                    ],
                    "total_hours": 2
                },
                {
                    "day": 3,
                    "date": "Day 3",
                    "theme": "复习日",
                    "blocks": [
                        {"time": "09:00-10:00", "task": "回顾 Day 1-2 内容", "type": "review", "priority": "medium"}
                    ],
                    "total_hours": 1,
                    "notes": "间隔复习"
                }
            ]
        }
    }
    ```
    '''

    result = parse_schedule(llm_response)
    schedule = result["schedule"]
    assert schedule["total_days"] == 3
    assert len(schedule["daily_plans"]) == 3
    assert schedule["daily_plans"][0]["theme"] == "LangChain 基础"
    assert schedule["daily_plans"][2]["blocks"][0]["type"] == "review"
    print("[OK] 日程解析成功")

    # 测试解析失败
    result2 = parse_schedule("这不是 JSON")
    assert "raw_schedule" in result2
    print("[OK] 解析失败返回原始文本")
    print()


def test_format_schedule():
    """测试日程格式化。"""
    print("=" * 60)
    print("测试 3: 格式化日程")
    print("=" * 60)

    schedule_data = {
        "schedule": {
            "total_days": 2,
            "daily_plans": [
                {
                    "day": 1,
                    "theme": "LangChain 基础",
                    "blocks": [
                        {"time": "09:00-11:00", "task": "看文档", "type": "learn", "priority": "high"},
                        {"time": "14:00-16:00", "task": "刷题", "type": "practice", "priority": "medium"},
                    ],
                    "total_hours": 4,
                },
                {
                    "day": 2,
                    "theme": "复习",
                    "blocks": [
                        {"time": "09:00-10:00", "task": "回顾", "type": "review", "priority": "low"},
                    ],
                    "total_hours": 1,
                    "notes": "轻松一天",
                },
            ],
        }
    }

    report = format_schedule(schedule_data)

    assert "LangChain" in report
    assert "复习" in report
    assert "🔴" in report or "🟡" in report
    assert "🔄" in report  # review icon
    print("[OK] 日程格式化成功")

    print(f"\n报告预览:\n{'-' * 40}")
    print(report[:800])
    print(f"{'-' * 40}\n")


def test_generate_ics():
    """测试 ICS 生成。"""
    print("=" * 60)
    print("测试 4: ICS 导出")
    print("=" * 60)

    schedule_data = {
        "schedule": {
            "daily_plans": [
                {
                    "day": 1,
                    "blocks": [
                        {"time": "09:00-11:00", "task": "学习 LangChain", "type": "learn"},
                    ],
                },
            ],
        }
    }

    ics = generate_ics(schedule_data, "2026-08-25")

    assert "BEGIN:VCALENDAR" in ics
    assert "END:VCALENDAR" in ics
    assert "学习" in ics
    assert "20260825" in ics
    print("[OK] ICS 生成成功")
    print()


# === 进度追踪测试 ===

def test_checkin_prompt():
    """测试签到 prompt 构建。"""
    print("=" * 60)
    print("测试 5: 签到 Prompt 构建")
    print("=" * 60)

    profile = CareerProfile()
    profile.plan = {
        "roadmap": {
            "phases": [{"name": "基础", "type": "learn", "milestones": []}]
        },
        "progress_log": [],
    }

    prompt = build_checkin_prompt(profile, "今天看了 LangChain 文档，跑了 quickstart")

    assert "LangChain" in prompt
    assert "签到" in prompt or "汇报" in prompt
    print("[OK] 签到 prompt 构建成功")
    print()


def test_parse_checkin():
    """测试签到解析。"""
    print("=" * 60)
    print("测试 6: 解析签到响应")
    print("=" * 60)

    llm_response = '''
    ```json
    {
        "completed_tasks": ["看 LangChain 文档", "跑通 quickstart"],
        "progress_pct": 30,
        "time_spent": "3小时",
        "blockers": [],
        "morale": "high",
        "deviation": {
            "on_track": true,
            "days_ahead_or_behind": 0,
            "reason": "进度正常"
        },
        "next_steps": ["开始做示例项目"],
        "adjustments": {"needed": false}
    }
    ```
    '''

    result = parse_checkin_response(llm_response)
    assert result["progress_pct"] == 30
    assert len(result["completed_tasks"]) == 2
    assert result["morale"] == "high"
    assert result["deviation"]["on_track"] is True
    print("[OK] 签到解析成功")
    print()


def test_format_checkin():
    """测试签到报告格式化。"""
    print("=" * 60)
    print("测试 7: 格式化签到报告")
    print("=" * 60)

    checkin_data = {
        "completed_tasks": ["看文档", "跑 quickstart"],
        "progress_pct": 30,
        "time_spent": "3小时",
        "blockers": ["环境配置花了很久"],
        "morale": "high",
        "deviation": {"on_track": True, "days_ahead_or_behind": 0, "reason": "正常"},
        "next_steps": ["做示例项目"],
        "adjustments": {"needed": False},
    }

    report = format_checkin_report(checkin_data)

    assert "30%" in report
    assert "看文档" in report
    assert "💪" in report
    assert "环境配置" in report
    print("[OK] 签到报告格式化成功")

    print(f"\n报告预览:\n{'-' * 40}")
    print(report[:600])
    print(f"{'-' * 40}\n")


def test_save_checkin():
    """测试签到保存。"""
    print("=" * 60)
    print("测试 8: 保存签到记录")
    print("=" * 60)

    profile = CareerProfile()
    profile.plan = {"roadmap": {"phases": []}}

    checkin_data = {
        "completed_tasks": ["任务1"],
        "progress_pct": 25,
        "morale": "neutral",
    }

    profile = save_checkin(profile, checkin_data)

    assert len(profile.plan["progress_log"]) == 1
    assert profile.plan["current_progress"] == 25
    assert profile.plan["progress_log"][0]["completed_tasks"] == ["任务1"]
    print("[OK] 签到保存成功")
    print()


def test_progress_overview():
    """测试进度概览。"""
    print("=" * 60)
    print("测试 9: 进度概览")
    print("=" * 60)

    profile = CareerProfile()
    profile.plan = {
        "current_progress": 45,
        "progress_log": [
            {"timestamp": "2026-08-20T10:00:00", "progress_pct": 20, "morale": "high", "completed_tasks": ["t1"]},
            {"timestamp": "2026-08-21T10:00:00", "progress_pct": 45, "morale": "neutral", "completed_tasks": ["t2", "t3"]},
        ],
        "roadmap": {
            "phases": [
                {"name": "基础", "type": "learn", "milestones": [{"name": "M1", "duration": "1周"}]},
            ],
        },
    }

    report = format_progress_overview(profile)

    assert "45%" in report
    assert "2 次" in report or "2次" in report
    assert "基础" in report
    print("[OK] 进度概览格式化成功")
    print()


# === 市场搜索测试 ===

def test_market_search():
    """测试市场搜索。"""
    print("=" * 60)
    print("测试 10: 市场搜索")
    print("=" * 60)

    # 测试面经搜索
    result = search_market_data("字节跳动 Agent 开发面经")
    assert result["search_type"] == "interview_experiences"
    print(f"[OK] 面经搜索类型推断正确: {result['search_type']}")

    # 测试薪资搜索
    result2 = search_market_data("AI Agent 岗位薪资")
    assert result2["search_type"] == "market_trends"
    print(f"[OK] 薪资搜索类型推断正确: {result2['search_type']}")

    # 测试 prompt 构建
    prompt = build_market_search_prompt("AI Agent 薪资", result2)
    assert "AI Agent" in prompt
    print("[OK] 市场搜索 prompt 构建成功")
    print()


# === MCP Tools 测试 ===

def test_mcp_tools():
    """测试 MCP tools 注册。"""
    print("=" * 60)
    print("测试 11: MCP Tools 注册")
    print("=" * 60)

    from src.server import mcp

    tools = [t.name for t in mcp._tool_manager.list_tools()]

    expected = ["generate_schedule", "save_schedule", "export_ics",
                "track_progress", "save_checkin", "view_progress",
                "search_market"]

    for t in expected:
        assert t in tools, f"{t} 未注册"
        print(f"[OK] {t} 已注册")

    print()


def main():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("日程 + 进度 + 市场搜索 测试套件")
    print("=" * 60 + "\n")

    tests = [
        test_schedule_sop_config,
        test_parse_schedule,
        test_format_schedule,
        test_generate_ics,
        test_checkin_prompt,
        test_parse_checkin,
        test_format_checkin,
        test_save_checkin,
        test_progress_overview,
        test_market_search,
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
