"""任务管理——任务创建、打卡辅助、阶段视图。

产品不规划时间：任务只有顺序和状态，进度以阶段为刻度。
"""

from __future__ import annotations

from typing import Any

from ..models import (
    CareerProfile,
    CheckIn,
    Task,
    TaskStatus,
)


def next_task_id(profile: CareerProfile) -> str:
    """生成不冲突的任务 ID：现有最大编号 + 1。"""
    max_num = 0
    for task in profile.tasks:
        if task.id.startswith("task_"):
            try:
                max_num = max(max_num, int(task.id[5:]))
            except ValueError:
                continue
    return f"task_{max_num + 1:03d}"


def create_tasks_from_roadmap(profile: CareerProfile) -> list[Task]:
    """从路线图生成任务列表。

    任务 schema 与 sop/roadmap.yaml 的 output_schema 一致：
    {name, description, priority}。

    Args:
        profile: 用户职业档案

    Returns:
        生成的任务列表
    """
    roadmap = profile.plan.get("roadmap", profile.plan)
    phases = roadmap.get("phases", [])

    tasks = []

    for phase_idx, phase in enumerate(phases):
        phase_id = phase.get("id") or f"phase_{phase_idx + 1}"
        phase_name = phase.get("name", f"阶段 {phase_idx + 1}")

        for ms_idx, milestone in enumerate(phase.get("milestones", [])):
            ms_name = milestone.get("name", f"里程碑 {ms_idx + 1}")
            ms_id = milestone.get("id") or f"{phase_id}_ms_{ms_idx + 1}"

            # 从里程碑的 tasks 字段生成任务
            for task_def in milestone.get("tasks", []):
                task = Task(
                    id=next_task_id_for(tasks),
                    name=task_def.get("name", ""),
                    description=task_def.get("description", ""),
                    phase_id=phase_id,
                    milestone_id=ms_id,
                    priority=task_def.get("priority", "medium"),
                )
                tasks.append(task)

            # 如果里程碑没有 tasks 字段，用里程碑本身作为任务
            if not milestone.get("tasks"):
                tasks.append(Task(
                    id=next_task_id_for(tasks),
                    name=ms_name,
                    description=milestone.get("description", ""),
                    phase_id=phase_id,
                    milestone_id=ms_id,
                    priority="medium",
                ))

        # 阶段没有任何可执行内容时，用阶段名兜底，保证阶段可追踪
        phase_task_count = sum(1 for t in tasks if t.phase_id == phase_id)
        if phase_task_count == 0:
            tasks.append(Task(
                id=next_task_id_for(tasks),
                name=f"推进阶段：{phase_name}",
                description=phase.get("goal", ""),
                phase_id=phase_id,
                priority="medium",
            ))

    return tasks


def next_task_id_for(existing: list[Task]) -> str:
    """在构建中的列表里生成下一个任务 ID。"""
    max_num = 0
    for task in existing:
        if task.id.startswith("task_"):
            try:
                max_num = max(max_num, int(task.id[5:]))
            except ValueError:
                continue
    return f"task_{max_num + 1:03d}"


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


def record_capability_evidence(
    profile: CareerProfile,
    task: Task,
    notes: str = "",
) -> dict[str, Any]:
    """将完成任务沉淀为能力证据，写入 have.capability_evidence。

    用户完成的任务是真实水平的佐证，目标变更重新分析时自动成为输入。

    Returns:
        写入的证据条目
    """
    entry = {
        "task": task.name,
        "milestone": task.milestone_id,
        "completed_at": task.completed_at or "",
    }
    if notes:
        entry["notes"] = notes

    have = profile.have
    evidence_list = have.setdefault("capability_evidence", [])
    if isinstance(evidence_list, list):
        evidence_list.append(entry)

    profile.section_updated_at["have"] = profile.updated_at
    return entry


def collect_completed_evidence(profile: CareerProfile) -> list[dict[str, Any]]:
    """重建任务前调用：把已完成/已跳过任务的进度沉淀为能力证据。"""
    entries: list[dict[str, Any]] = []
    finished = [t for t in profile.tasks if t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)]
    checkin_notes = {c.task_id: c.notes for c in profile.checkins}

    for task in finished:
        entry = {
            "task": task.name,
            "phase": task.phase_id,
            "status": task.status,
            "completed_at": task.completed_at or "",
        }
        notes = checkin_notes.get(task.id, "")
        if notes:
            entry["notes"] = notes
        entries.append(entry)

    return entries


def current_phase_view(profile: CareerProfile) -> dict[str, Any] | None:
    """定位当前阶段：第一个存在未完成任务的阶段。

    Returns:
        {"phase_id", "phase_name", "next_tasks", "done", "total"}，
        全部完成时返回 None。
    """
    done_status = (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
    for task in profile.tasks:
        if task.status not in done_status:
            break
    else:
        return None

    roadmap = profile.plan.get("roadmap", profile.plan)
    phases = roadmap.get("phases", [])
    phase_names = {}
    for idx, phase in enumerate(phases):
        phase_id = phase.get("id") or f"phase_{idx + 1}"
        phase_names[phase_id] = phase.get("name", phase_id)

    first_open = next(t for t in profile.tasks if t.status not in done_status)
    phase_id = first_open.phase_id

    phase_tasks = [t for t in profile.tasks if t.phase_id == phase_id]
    open_tasks = [t for t in phase_tasks if t.status not in done_status]

    return {
        "phase_id": phase_id,
        "phase_name": phase_names.get(phase_id, phase_id),
        "next_tasks": open_tasks[:5],
        "done": len(phase_tasks) - len(open_tasks),
        "total": len(phase_tasks),
    }


def format_task_list(tasks: list[Task], title: str = "任务列表") -> str:
    """格式化任务列表。"""
    lines = [f"## {title}", ""]

    if not tasks:
        lines.append("暂无任务")
        return "\n".join(lines)

    # 按状态分组
    pending = [t for t in tasks if t.status == TaskStatus.PENDING]
    in_progress = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]
    completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]
    skipped = [t for t in tasks if t.status == TaskStatus.SKIPPED]

    if in_progress:
        lines.append("### 进行中")
        for t in in_progress:
            lines.append(f"-  **{t.name}** (ID: {t.id})")
        lines.append("")

    if pending:
        lines.append("### 待办")
        for t in pending:
            icon = {"high": "[高]", "medium": "[中]", "low": "[低]"}.get(t.priority, "[中]")
            lines.append(f"- {icon} **{t.name}** (ID: {t.id})")
        lines.append("")

    if completed:
        lines.append("### 已完成")
        for t in completed:
            lines.append(f"-  {t.name}")
        lines.append("")

    if skipped:
        lines.append("### 已跳过")
        for t in skipped:
            lines.append(f"- {t.name}")
        lines.append("")

    return "\n".join(lines)


def format_progress_overview(profile: CareerProfile) -> str:
    """格式化整体进度概览。"""
    total = len(profile.tasks)
    completed = sum(1 for t in profile.tasks if t.status == TaskStatus.COMPLETED)
    in_progress = sum(1 for t in profile.tasks if t.status == TaskStatus.IN_PROGRESS)
    pending = sum(1 for t in profile.tasks if t.status == TaskStatus.PENDING)
    skipped = sum(1 for t in profile.tasks if t.status == TaskStatus.SKIPPED)

    pct = int(completed / total * 100) if total > 0 else 0
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)

    lines = [
        f"## 整体进度：{pct}% [{bar}]",
        "",
        f"总计 {total} 个任务：",
        f"-  已完成：{completed}",
        f"-  进行中：{in_progress}",
        f"-  待办：{pending}",
    ]
    if skipped:
        lines.append(f"- 已跳过：{skipped}")
    lines += ["", f"共打卡 {len(profile.checkins)} 次", ""]

    return "\n".join(lines)
