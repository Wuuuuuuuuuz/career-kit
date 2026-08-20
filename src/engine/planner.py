"""规划引擎——路线图和日程的核心逻辑。

本模块提供结构和约束，LLM 提供智能。
引擎确保：
- 任务在可用时间内分配
- 阶段之间的依赖关系被尊重
- 记录进度后日程自动调整
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def distribute_tasks(
    tasks: list[dict[str, Any]],
    available_hours: dict[str, float],
    start_date: str,
) -> list[dict[str, Any]]:
    """将任务分配到可用时间段（贪心调度）。

    算法：
    1. 按优先级排序（high > medium > low）
    2. 拓扑排序尊重 depends_on 依赖
    3. 贪心分配到第一个有足够时间的日期

    Args:
        tasks: 任务列表，每项含：
            - id: 任务唯一标识
            - estimated_hours: 预估耗时
            - priority: high/medium/low
            - depends_on: 依赖的任务 id 列表（可选）
        available_hours: 日期到可用小时数的映射 {"2026-08-25": 4.0, ...}
        start_date: 开始排期的日期（YYYY-MM-DD）

    Returns:
        分配了日期的任务列表，每项增加：
        - scheduled_date: 分配的日期
        - scheduled_hours: 实际分配的小时数
    """
    if not tasks or not available_hours:
        return []

    # 按日期排序
    sorted_dates = sorted(available_hours.keys())
    if not sorted_dates:
        return []

    # 构建依赖图
    task_map = {t["id"]: t for t in tasks}
    in_degree: dict[str, int] = {t["id"]: 0 for t in tasks}
    for t in tasks:
        for dep in t.get("depends_on", []):
            if dep in task_map:
                in_degree[t["id"]] += 1

    # 优先级权重
    priority_weight = {"high": 0, "medium": 1, "low": 2}

    # 拓扑排序 + 优先级排序
    ready = sorted(
        [t["id"] for t in tasks if in_degree[t["id"]] == 0],
        key=lambda tid: priority_weight.get(task_map[tid].get("priority", "medium"), 1),
    )

    scheduled: list[dict[str, Any]] = []
    remaining_hours = dict(available_hours)  # 剩余可用时间
    completed: set[str] = set()

    while ready:
        task_id = ready.pop(0)
        task = task_map[task_id]
        hours_needed = task.get("estimated_hours", 1.0)

        # 找第一个有足够时间的日期
        assigned = False
        for date in sorted_dates:
            if remaining_hours.get(date, 0) >= hours_needed:
                result = dict(task)
                result["scheduled_date"] = date
                result["scheduled_hours"] = hours_needed
                scheduled.append(result)
                remaining_hours[date] -= hours_needed
                completed.add(task_id)
                assigned = True
                break

        if not assigned:
            # 时间不够，分配到最后一天（部分时间）
            last_date = sorted_dates[-1]
            result = dict(task)
            result["scheduled_date"] = last_date
            result["scheduled_hours"] = remaining_hours.get(last_date, 0)
            scheduled.append(result)
            remaining_hours[last_date] = 0
            completed.add(task_id)

        # 检查是否有新的任务就绪
        for t in tasks:
            if t["id"] in completed or t["id"] in ready:
                continue
            deps = t.get("depends_on", [])
            if all(d in completed for d in deps):
                ready.append(t["id"])
        # 重新排序
        ready.sort(key=lambda tid: priority_weight.get(task_map[tid].get("priority", "medium"), 1))

    return scheduled


def recalculate_after_progress(
    plan: dict[str, Any],
    completed_task_id: str,
    actual_hours: float,
) -> dict[str, Any]:
    """完成一个任务后，调整剩余计划。

    算法（方差调整）：
    1. 计算效率比 = 实际耗时 / 预估耗时
    2. 用指数平滑修正后续任务的估算：new_est = old_est * (0.7 * ratio + 0.3)
    3. 更新任务状态

    Args:
        plan: 当前计划数据（含 tasks 列表）
        completed_task_id: 完成的任务 id
        actual_hours: 实际耗时（用于修正后续估算）

    Returns:
        调整后的计划
    """
    tasks = plan.get("tasks", [])
    if not tasks:
        return plan

    # 找到完成的任务
    completed_task = None
    for t in tasks:
        if t.get("id") == completed_task_id:
            completed_task = t
            break

    if not completed_task:
        return plan

    # 标记完成
    completed_task["status"] = "completed"
    completed_task["actual_hours"] = actual_hours

    # 计算效率比
    estimated = completed_task.get("estimated_hours", 1.0)
    if estimated > 0:
        ratio = actual_hours / estimated
    else:
        ratio = 1.0

    # 指数平滑修正后续任务
    smoothing = 0.3
    adjustment_factor = 0.7 * ratio + smoothing

    for t in tasks:
        if t.get("status") == "completed":
            continue
        old_est = t.get("estimated_hours", 1.0)
        t["estimated_hours"] = round(old_est * adjustment_factor, 1)

    # 记录调整历史
    if "adjustment_log" not in plan:
        plan["adjustment_log"] = []

    plan["adjustment_log"].append({
        "task_id": completed_task_id,
        "estimated": estimated,
        "actual": actual_hours,
        "ratio": round(ratio, 2),
        "adjustment_factor": round(adjustment_factor, 2),
    })

    return plan
