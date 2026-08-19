"""规划引擎——路线图和日程的核心逻辑。

本模块提供结构和约束，LLM 提供智能。
引擎确保：
- 任务在可用时间内分配
- 阶段之间的依赖关系被尊重
- 记录进度后日程自动调整
"""

from datetime import datetime, timedelta
from typing import Any


def distribute_tasks(
    tasks: list[dict[str, Any]],
    available_hours: dict[str, float],
    start_date: str,
) -> list[dict[str, Any]]:
    """将任务分配到可用时间段。

    Args:
        tasks: 任务列表，每项含 estimated_hours
        available_hours: 日期到可用小时数的映射
        start_date: 开始排期的日期

    Returns:
        分配了日期的任务列表
    """
    # TODO: 贪心分配，尊重任务依赖
    return []


def recalculate_after_progress(
    plan: dict[str, Any],
    completed_task_id: str,
    actual_hours: float,
) -> dict[str, Any]:
    """完成一个任务后，调整剩余计划。

    Args:
        plan: 当前计划数据
        completed_task_id: 完成的任务 id
        actual_hours: 实际耗时（用于修正后续估算）

    Returns:
        调整后的计划
    """
    # TODO: 更新估算，根据进度快慢调整后续任务
    return plan
