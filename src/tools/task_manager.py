"""任务管理——任务创建、打卡、调整。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from ..models import (
    Adjustment,
    CareerProfile,
    CheckIn,
    Task,
    TaskStatus,
)


def create_tasks_from_roadmap(profile: CareerProfile) -> list[Task]:
    """从路线图生成任务列表。

    Args:
        profile: 用户职业档案

    Returns:
        生成的任务列表
    """
    roadmap = profile.plan.get("roadmap", profile.plan)
    phases = roadmap.get("phases", [])

    tasks = []
    task_id = 1

    for phase_idx, phase in enumerate(phases):
        phase_name = phase.get("name", f"阶段 {phase_idx + 1}")
        phase_id = f"phase_{phase_idx + 1}"

        for ms_idx, milestone in enumerate(phase.get("milestones", [])):
            ms_name = milestone.get("name", f"里程碑 {ms_idx + 1}")
            ms_id = f"{phase_id}_ms_{ms_idx + 1}"

            # 从里程碑的 tasks 字段生成任务
            for task_def in milestone.get("tasks", []):
                task = Task(
                    id=f"task_{task_id:03d}",
                    name=task_def.get("name", ""),
                    description=task_def.get("description", ""),
                    phase_id=phase_id,
                    milestone_id=ms_id,
                    estimated_days=task_def.get("estimated_days", 1),
                    priority=task_def.get("priority", "medium"),
                )
                tasks.append(task)
                task_id += 1

            # 如果里程碑没有 tasks 字段，用里程碑本身作为任务
            if not milestone.get("tasks"):
                duration_days = _parse_duration(milestone.get("duration", "1天"))
                task = Task(
                    id=f"task_{task_id:03d}",
                    name=ms_name,
                    description=milestone.get("description", ""),
                    phase_id=phase_id,
                    milestone_id=ms_id,
                    estimated_days=duration_days,
                    priority="medium",
                )
                tasks.append(task)
                task_id += 1

    return tasks


def _parse_duration(duration_str: str) -> int:
    """解析时长字符串为天数。

    Args:
        duration_str: 时长字符串，如 "2周", "3天", "1个月"

    Returns:
        天数
    """
    duration_str = duration_str.strip()

    if "周" in duration_str:
        try:
            weeks = int(duration_str.replace("周", "").strip())
            return weeks * 7
        except ValueError:
            return 7
    elif "月" in duration_str:
        try:
            months = int(duration_str.replace("个月", "").replace("月", "").strip())
            return months * 30
        except ValueError:
            return 30
    elif "天" in duration_str:
        try:
            return int(duration_str.replace("天", "").strip())
        except ValueError:
            return 1
    else:
        try:
            return int(duration_str)
        except ValueError:
            return 1


def set_deadlines(tasks: list[Task], start_date: str | None = None) -> list[Task]:
    """为任务设置截止日期。

    Args:
        tasks: 任务列表
        start_date: 开始日期，格式为 ISO 格式，默认为今天

    Returns:
        更新后的任务列表
    """
    if start_date:
        current_date = datetime.fromisoformat(start_date)
    else:
        current_date = datetime.now()

    for task in tasks:
        task.deadline = current_date.isoformat()
        current_date += timedelta(days=max(1, int(task.estimated_days)))

    return tasks


def checkin_task(
    profile: CareerProfile,
    task_id: str,
    status: str = TaskStatus.COMPLETED,
    notes: str = "",
) -> tuple[CareerProfile, CheckIn]:
    """打卡任务。

    Args:
        profile: 用户职业档案
        task_id: 任务 ID
        status: 打卡状态（completed, skipped）
        notes: 备注

    Returns:
        (更新后的档案, 打卡记录)
    """
    task = profile.get_task(task_id)
    if not task:
        raise ValueError(f"任务 {task_id} 不存在")

    # 更新任务状态
    if status == TaskStatus.COMPLETED:
        task.complete()
    elif status == TaskStatus.SKIPPED:
        task.skip(notes)
    else:
        raise ValueError(f"无效的打卡状态: {status}")

    # 创建打卡记录
    checkin = CheckIn(
        task_id=task_id,
        status=status,
        notes=notes,
    )

    profile.add_checkin(checkin)
    profile.touch()

    return profile, checkin


def check_overdue_tasks(profile: CareerProfile) -> list[Task]:
    """检查超期任务。

    Args:
        profile: 用户职业档案

    Returns:
        超期任务列表
    """
    overdue = []
    for task in profile.tasks:
        if task.is_overdue():
            task.status = TaskStatus.OVERDUE
            overdue.append(task)
    return overdue


def compress_schedule(profile: CareerProfile, overdue_days: float) -> list[dict[str, Any]]:
    """压缩后续任务时长。

    Args:
        profile: 用户职业档案
        overdue_days: 超期天数

    Returns:
        调整记录列表
    """
    pending_tasks = [t for t in profile.tasks if t.status == TaskStatus.PENDING]
    if not pending_tasks:
        return []

    # 计算每个任务需要压缩的天数
    compress_per_task = overdue_days / len(pending_tasks)
    changes = []

    for task in pending_tasks:
        old_days = task.estimated_days
        new_days = max(0.5, old_days - compress_per_task)
        task.estimated_days = round(new_days, 1)

        changes.append({
            "type": "compress_task",
            "task_id": task.id,
            "task_name": task.name,
            "old_days": old_days,
            "new_days": new_days,
        })

    # 重新计算截止日期
    _recalculate_deadlines(profile)

    return changes


def _recalculate_deadlines(profile: CareerProfile) -> None:
    """重新计算所有待办任务的截止日期。"""
    pending_tasks = [t for t in profile.tasks if t.status == TaskStatus.PENDING]
    if not pending_tasks:
        return

    current_date = datetime.now()
    for task in pending_tasks:
        task.deadline = current_date.isoformat()
        current_date += timedelta(days=max(1, int(task.estimated_days)))


def add_depth_tasks(profile: CareerProfile, task_id: str) -> list[Task]:
    """为提前完成的任务添加深度任务。

    Args:
        profile: 用户职业档案
        task_id: 提前完成的任务 ID

    Returns:
        新增的任务列表
    """
    task = profile.get_task(task_id)
    if not task:
        return []

    # 创建一个深度任务
    depth_task = Task(
        id=f"task_{len(profile.tasks) + 1:03d}",
        name=f"{task.name}（深入）",
        description=f"深入学习 {task.name} 的高级内容",
        phase_id=task.phase_id,
        milestone_id=task.milestone_id,
        estimated_days=task.estimated_days,
        priority=task.priority,
    )

    profile.add_task(depth_task)
    return [depth_task]


def format_task_list(tasks: list[Task], title: str = "任务列表") -> str:
    """格式化任务列表。

    Args:
        tasks: 任务列表
        title: 标题

    Returns:
        格式化的 Markdown 文本
    """
    lines = [f"## {title}", ""]

    if not tasks:
        lines.append("暂无任务")
        return "\n".join(lines)

    # 按状态分组
    pending = [t for t in tasks if t.status == TaskStatus.PENDING]
    in_progress = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]
    completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]
    overdue = [t for t in tasks if t.status == TaskStatus.OVERDUE]

    if in_progress:
        lines.append("### 进行中")
        for t in in_progress:
            lines.append(f"- 🔵 **{t.name}** (ID: {t.id})")
            if t.deadline:
                lines.append(f"  截止: {t.deadline[:10]}")
        lines.append("")

    if pending:
        lines.append("### 待办")
        for t in pending:
            lines.append(f"- ⚪ **{t.name}** (ID: {t.id})")
            if t.deadline:
                lines.append(f"  截止: {t.deadline[:10]}")
            lines.append(f"  预计: {t.estimated_days}天")
        lines.append("")

    if overdue:
        lines.append("### ⚠️ 超期")
        for t in overdue:
            days = t.days_overdue()
            lines.append(f"- 🔴 **{t.name}** (ID: {t.id}) - 超期 {days:.1f} 天")
        lines.append("")

    if completed:
        lines.append("### ✅ 已完成")
        for t in completed:
            lines.append(f"- ✅ {t.name}")
        lines.append("")

    return "\n".join(lines)


def format_progress_overview(profile: CareerProfile) -> str:
    """格式化进度概览。

    Args:
        profile: 用户职业档案

    Returns:
        格式化的进度概览
    """
    lines = []

    # 统计
    total = len(profile.tasks)
    completed = len([t for t in profile.tasks if t.status == TaskStatus.COMPLETED])
    in_progress = len([t for t in profile.tasks if t.status == TaskStatus.IN_PROGRESS])
    pending = len([t for t in profile.tasks if t.status == TaskStatus.PENDING])
    overdue = len([t for t in profile.tasks if t.status == TaskStatus.OVERDUE])

    # 进度条
    pct = int(completed / total * 100) if total > 0 else 0
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)

    lines.append(f"## 📊 整体进度：{pct}% [{bar}]")
    lines.append("")
    lines.append(f"总计 {total} 个任务：")
    lines.append(f"- ✅ 已完成：{completed}")
    lines.append(f"- 🔵 进行中：{in_progress}")
    lines.append(f"- ⚪ 待办：{pending}")
    if overdue > 0:
        lines.append(f"- 🔴 超期：{overdue}")
    lines.append("")

    # 打卡统计
    lines.append(f"共打卡 {len(profile.checkins)} 次")
    lines.append("")

    return "\n".join(lines)
