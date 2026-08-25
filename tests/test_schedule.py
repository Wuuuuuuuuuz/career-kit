"""日程生成 + 任务追踪测试。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8')

from src.models import CareerProfile
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


# === 日程生成测试 ===

def test_schedule_sop_config():
    """测试日程方法论配置。"""
    print("=" * 60)
    print("测试 1: 日程方法论配置")
    print("=" * 60)

    from src.tools.methodology import load_methodology
    m = load_methodology("schedule")
    assert m["name"] == "日程生成"
    phases = m["methodology"]["phases"]
    assert len(phases) >= 2
    print(f"[OK] 日程方法论加载成功，{len(phases)} 阶段")
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


# === 任务追踪测试 ===

def test_create_tasks_from_roadmap():
    """测试从路线图生成任务。"""
    print("=" * 60)
    print("测试 5: 从路线图生成任务")
    print("=" * 60)

    profile = CareerProfile()
    profile.plan = {
        "roadmap": {
            "phases": [
                {
                    "name": "基础",
                    "milestones": [
                        {
                            "name": "LangChain 入门",
                            "duration": "3天",
                            "tasks": [
                                {"name": "看官方文档", "estimated_days": 1},
                                {"name": "跑通 quickstart", "estimated_days": 2},
                            ],
                        },
                    ],
                },
            ],
        },
    }

    tasks = create_tasks_from_roadmap(profile)
    assert len(tasks) == 2
    assert tasks[0].name == "看官方文档"
    assert tasks[0].phase_id == "phase_1"
    print(f"[OK] 生成 {len(tasks)} 个任务")
    print()


def test_checkin_task_flow():
    """测试任务打卡流程。"""
    print("=" * 60)
    print("测试 6: 任务打卡")
    print("=" * 60)

    profile = CareerProfile()
    profile.plan = {
        "roadmap": {
            "phases": [
                {
                    "name": "基础",
                    "milestones": [
                        {"name": "M1", "duration": "1天", "tasks": [{"name": "任务1", "estimated_days": 1}]},
                    ],
                },
            ],
        },
    }
    tasks = create_tasks_from_roadmap(profile)
    for t in tasks:
        profile.add_task(t)

    # 打卡完成
    profile, checkin = do_checkin(profile, tasks[0].id, "completed", notes="测试")

    assert len(profile.checkins) == 1
    assert profile.checkins[0].task_id == tasks[0].id
    assert profile.tasks[0].status == "completed"
    print(f"[OK] 任务 {tasks[0].id} 打卡成功，状态: {profile.tasks[0].status}")
    print()


def test_progress_overview():
    """测试进度概览（任务级）。"""
    print("=" * 60)
    print("测试 7: 进度概览")
    print("=" * 60)

    profile = CareerProfile()
    profile.plan = {
        "roadmap": {
            "phases": [
                {
                    "name": "基础",
                    "milestones": [
                        {"name": "M1", "duration": "1天", "tasks": [{"name": "任务1", "estimated_days": 1}]},
                        {"name": "M2", "duration": "1天", "tasks": [{"name": "任务2", "estimated_days": 1}]},
                    ],
                },
            ],
        },
    }
    tasks = create_tasks_from_roadmap(profile)
    for t in tasks:
        profile.add_task(t)
    profile, _ = do_checkin(profile, tasks[0].id, "completed")

    report = format_progress_overview(profile)

    assert "任务" in report
    assert "已完成" in report
    print("[OK] 进度概览格式化成功")
    print()


# === MCP Tools 测试 ===

def test_mcp_tools():
    """测试 MCP tools 注册。"""
    print("=" * 60)
    print("测试 8: MCP Tools 注册")
    print("=" * 60)

    from src.server import mcp

    tools = [t.name for t in mcp._tool_manager.list_tools()]

    expected = ["generate_schedule", "save_schedule", "export_ics",
                "generate_tasks", "get_today_tasks", "checkin_task",
                "trigger_insight", "apply_insight", "get_progress"]

    for t in expected:
        assert t in tools, f"{t} 未注册"
        print(f"[OK] {t} 已注册")

    print()


def main():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("日程 + 任务追踪 测试套件")
    print("=" * 60 + "\n")

    tests = [
        test_schedule_sop_config,
        test_parse_schedule,
        test_format_schedule,
        test_generate_ics,
        test_create_tasks_from_roadmap,
        test_checkin_task_flow,
        test_progress_overview,
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
