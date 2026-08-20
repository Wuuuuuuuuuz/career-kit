"""规划引擎测试——贪心调度 + 方差调整。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src.engine.planner import distribute_tasks, recalculate_after_progress


def test_basic_distribution():
    """基础调度：3 个任务分配到 2 天。"""
    print("=" * 60)
    print("测试 1: 基础调度")
    print("=" * 60)

    tasks = [
        {"id": "t1", "task": "看文档", "estimated_hours": 3, "priority": "high"},
        {"id": "t2", "task": "跑 demo", "estimated_hours": 2, "priority": "medium"},
        {"id": "t3", "task": "写笔记", "estimated_hours": 1, "priority": "low"},
    ]
    available = {"2026-08-25": 4.0, "2026-08-26": 3.0}

    result = distribute_tasks(tasks, available, "2026-08-25")

    assert len(result) == 3
    # 高优先级应该先分配
    assert result[0]["id"] == "t1"
    assert result[0]["scheduled_date"] == "2026-08-25"
    # t2 也应在第一天（3+2=5 > 4，所以 t2 应在第二天）
    assert result[1]["scheduled_date"] == "2026-08-26"
    print(f"[OK] 3 个任务分配成功")
    for r in result:
        print(f"  {r['id']}: {r['scheduled_date']} ({r['scheduled_hours']}h)")
    print()


def test_dependency_ordering():
    """依赖排序：t2 依赖 t1。"""
    print("=" * 60)
    print("测试 2: 依赖排序")
    print("=" * 60)

    tasks = [
        {"id": "t2", "task": "进阶", "estimated_hours": 2, "priority": "high", "depends_on": ["t1"]},
        {"id": "t1", "task": "基础", "estimated_hours": 2, "priority": "low"},
    ]
    available = {"2026-08-25": 2.0, "2026-08-26": 2.0}

    result = distribute_tasks(tasks, available, "2026-08-25")

    assert len(result) == 2
    # t1 虽然优先级低，但因为 t2 依赖它，应该先调度
    ids_in_order = [r["id"] for r in result]
    assert ids_in_order.index("t1") < ids_in_order.index("t2")
    print(f"[OK] 依赖排序正确: {[r['id'] for r in result]}")
    print()


def test_priority_ordering():
    """优先级排序：同一天内高优先级先调度。"""
    print("=" * 60)
    print("测试 3: 优先级排序")
    print("=" * 60)

    tasks = [
        {"id": "low", "task": "低", "estimated_hours": 1, "priority": "low"},
        {"id": "high", "task": "高", "estimated_hours": 1, "priority": "high"},
        {"id": "med", "task": "中", "estimated_hours": 1, "priority": "medium"},
    ]
    available = {"2026-08-25": 10.0}

    result = distribute_tasks(tasks, available, "2026-08-25")

    assert len(result) == 3
    assert result[0]["id"] == "high"
    assert result[1]["id"] == "med"
    assert result[2]["id"] == "low"
    print(f"[OK] 优先级排序: {[r['id'] for r in result]}")
    print()


def test_empty_input():
    """空输入处理。"""
    print("=" * 60)
    print("测试 4: 空输入")
    print("=" * 60)

    result1 = distribute_tasks([], {"2026-08-25": 4.0}, "2026-08-25")
    assert result1 == []
    print("[OK] 空任务列表返回 []")

    result2 = distribute_tasks([{"id": "t1", "estimated_hours": 1}], {}, "2026-08-25")
    assert result2 == []
    print("[OK] 空可用时间返回 []")
    print()


def test_time_overflow():
    """时间溢出：任务超出可用时间。"""
    print("=" * 60)
    print("测试 5: 时间溢出")
    print("=" * 60)

    tasks = [
        {"id": "t1", "task": "大任务", "estimated_hours": 10, "priority": "high"},
    ]
    available = {"2026-08-25": 2.0}

    result = distribute_tasks(tasks, available, "2026-08-25")

    assert len(result) == 1
    assert result[0]["scheduled_date"] == "2026-08-25"
    assert result[0]["scheduled_hours"] == 2.0  # 只分配了可用时间
    print(f"[OK] 溢出时分配可用时间: {result[0]['scheduled_hours']}h")
    print()


def test_recalculate_basic():
    """基础方差调整。"""
    print("=" * 60)
    print("测试 6: 方差调整")
    print("=" * 60)

    plan = {
        "tasks": [
            {"id": "t1", "estimated_hours": 2, "status": "pending"},
            {"id": "t2", "estimated_hours": 4, "status": "pending"},
            {"id": "t3", "estimated_hours": 3, "status": "pending"},
        ]
    }

    # t1 预估 2h，实际 3h（ratio = 1.5）
    result = recalculate_after_progress(plan, "t1", 3.0)

    assert result["tasks"][0]["status"] == "completed"
    assert result["tasks"][0]["actual_hours"] == 3.0

    # adjustment_factor = 0.7 * 1.5 + 0.3 = 1.35
    # t2: 4 * 1.35 = 5.4
    assert result["tasks"][1]["estimated_hours"] == 5.4
    # t3: 3 * 1.35 = 4.05 → round to 4.0 (浮点精度)
    assert abs(result["tasks"][2]["estimated_hours"] - 4.05) < 0.1

    assert len(result["adjustment_log"]) == 1
    print(f"[OK] 方差调整: ratio=1.5, factor=1.35")
    print(f"  t2: 4h → {result['tasks'][1]['estimated_hours']}h")
    print(f"  t3: 3h → {result['tasks'][2]['estimated_hours']}h")
    print()


def test_recalculate_fast():
    """快速完成的调整（实际 < 预估）。"""
    print("=" * 60)
    print("测试 7: 快速完成调整")
    print("=" * 60)

    plan = {
        "tasks": [
            {"id": "t1", "estimated_hours": 4, "status": "pending"},
            {"id": "t2", "estimated_hours": 6, "status": "pending"},
        ]
    }

    # t1 预估 4h，实际 2h（ratio = 0.5）
    result = recalculate_after_progress(plan, "t1", 2.0)

    # adjustment_factor = 0.7 * 0.5 + 0.3 = 0.65
    # t2: 6 * 0.65 = 3.9
    assert result["tasks"][1]["estimated_hours"] == 3.9
    print(f"[OK] 快速完成: ratio=0.5, factor=0.65")
    print(f"  t2: 6h → {result['tasks'][1]['estimated_hours']}h")
    print()


def test_recalculate_no_tasks():
    """无任务时的调整。"""
    print("=" * 60)
    print("测试 8: 无任务调整")
    print("=" * 60)

    plan = {"tasks": []}
    result = recalculate_after_progress(plan, "t1", 2.0)
    assert result == {"tasks": []}
    print("[OK] 空任务列表返回原样")

    plan2 = {"tasks": [{"id": "t1", "estimated_hours": 2}]}
    result2 = recalculate_after_progress(plan2, "nonexistent", 2.0)
    assert result2["tasks"][0].get("status") is None
    print("[OK] 不存在的任务 ID 返回原样")
    print()


def main():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("规划引擎测试套件")
    print("=" * 60 + "\n")

    tests = [
        test_basic_distribution,
        test_dependency_ordering,
        test_priority_ordering,
        test_empty_input,
        test_time_overflow,
        test_recalculate_basic,
        test_recalculate_fast,
        test_recalculate_no_tasks,
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
