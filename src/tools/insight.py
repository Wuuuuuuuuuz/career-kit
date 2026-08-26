"""洞察引擎——进度检查、阶段审计、调整建议。

触发方式只有两种：
- stage_audit：用户完成一个阶段后
- event：用户报告事件（如拿到面试）

产品不规划时间，洞察基于「完成数/总数」与用户事件，不做时间推定。
"""

from __future__ import annotations

import json
from typing import Any

from ..models import (
    Adjustment,
    CareerProfile,
    Task,
    TaskStatus,
)
from .task_manager import next_task_id


VALID_TRIGGER_TYPES = ("stage_audit", "event")


def build_insight_prompt(
    profile: CareerProfile,
    trigger_type: str = "stage_audit",
    event_description: str = "",
) -> str:
    """构建洞察分析的 LLM prompt。

    Args:
        profile: 用户职业档案
        trigger_type: 触发类型（stage_audit / event）
        event_description: 事件描述（当 trigger_type 为 event 时）

    Returns:
        prompt 字符串
    """
    total = len(profile.tasks)
    completed = sum(1 for t in profile.tasks if t.status == TaskStatus.COMPLETED)
    skipped = sum(1 for t in profile.tasks if t.status == TaskStatus.SKIPPED)

    # 各阶段完成情况
    roadmap = profile.plan.get("roadmap", profile.plan)
    phases = roadmap.get("phases", []) if roadmap else []
    phase_lines = []
    for idx, phase in enumerate(phases):
        phase_id = phase.get("id") or f"phase_{idx + 1}"
        phase_tasks = [t for t in profile.tasks if t.phase_id == phase_id]
        done = sum(1 for t in phase_tasks if t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED))
        name = phase.get("name", phase_id)
        phase_lines.append(f"- {name}（{phase_id}）：{done}/{len(phase_tasks)} 完成")
    phase_text = "\n".join(phase_lines) if phase_lines else "（无阶段信息）"

    # 近期打卡
    recent_checkins = profile.checkins[-5:] if profile.checkins else []
    checkin_text = json.dumps(
        [c.model_dump() for c in recent_checkins],
        ensure_ascii=False,
        indent=2,
    ) if recent_checkins else "（无打卡记录）"

    # 触发上下文
    if trigger_type == "stage_audit":
        trigger_context = "用户刚完成了当前阶段的任务，请审计该阶段成果，评估是否需要调整后续计划。"
    elif trigger_type == "event":
        trigger_context = f"用户报告了一个事件：{event_description}。请评估是否需要调整目标或计划。"
    else:
        trigger_context = "请检查用户整体进度，判断是否需要调整。"

    return f"""你是一个职业教练，负责分析用户的进度并提出调整建议。

## 当前档案
- 目标：{profile.want.get('target_role', '未设定')}
- 进度：{completed}/{total} 个任务已完成{f'，{skipped} 个跳过' if skipped else ''}

## 阶段完成情况
{phase_text}

## 近期打卡
{checkin_text}

## 能力证据
{json.dumps(profile.have.get('capability_evidence', []), ensure_ascii=False)}

## 触发原因
{trigger_context}

请分析用户进度，输出 JSON：
```json
{{
    "trigger_type": "{trigger_type}",
    "status": "on_track|behind|ahead|need_adjustment",
    "summary": "进度总结",
    "insights": [
        "洞察1",
        "洞察2"
    ],
    "adjustment_needed": true,
    "adjustment_type": "auto|manual",
    "adjustment_reason": "调整原因",
    "changes": [
        {{
            "type": "add_task|remove_task|modify_task|add_phase",
            "task_id": "被操作的任务 ID（add_task 时省略）",
            "description": "具体调整内容",
            "details": {{}}
        }}
    ],
    "user_message": "给用户的消息（鼓励/建议/警告）"
}}
```

分析要点：
1. 对比各阶段完成情况，判断推进节奏是否健康
2. 重点是基于「现实 vs 计划」的偏差调整**后续未执行的阶段计划**：
   - 执行不足（如预期进目标企业实习却未成）→ 增加/替换中间阶段（如先到另一家企业攒经历）
   - 执行超出预期（如意外进了更厉害的企业）→ 删减重复阶段、提升目标
   - 调整的是未来计划而非已执行部分——已执行的只记录事实与偏差，不评判
3. 如果某类任务反复跳过，建议调整内容或顺序
4. 结合能力证据评估真实水平是否匹配目标
5. 如果用户报告事件，评估目标是否需要调整
6. 给出鼓励或建议"""


def apply_adjustment(
    profile: CareerProfile,
    insight_result: dict[str, Any],
) -> tuple[CareerProfile, Adjustment]:
    """应用调整到档案。

    支持的变更类型：add_task / remove_task / modify_task。
    产品不规划时间，不存在压缩时长类调整。

    Returns:
        (更新后的档案, 调整记录)
    """
    changes = insight_result.get("changes", [])
    applied_changes = []

    for change in changes:
        change_type = change.get("type")
        task_id = change.get("task_id")

        if change_type == "add_task":
            details = change.get("details", {})
            new_task = Task(
                id=next_task_id(profile),
                name=details.get("name", change.get("description", "")),
                description=details.get("description", ""),
                phase_id=details.get("phase_id", ""),
                milestone_id=details.get("milestone_id", ""),
                priority=details.get("priority", "medium"),
            )
            profile.add_task(new_task)
            applied_changes.append({
                "type": "add_task",
                "task_id": new_task.id,
                "task_name": new_task.name,
            })

        elif change_type == "remove_task" and task_id:
            task = profile.get_task(task_id)
            if task:
                profile.tasks = [t for t in profile.tasks if t.id != task_id]
                applied_changes.append({
                    "type": "remove_task",
                    "task_id": task_id,
                    "task_name": task.name,
                })

        elif change_type == "modify_task" and task_id:
            task = profile.get_task(task_id)
            if task:
                details = change.get("details", {})
                if "name" in details:
                    task.name = details["name"]
                if "description" in details:
                    task.description = details["description"]
                if "priority" in details:
                    task.priority = details["priority"]
                applied_changes.append({
                    "type": "modify_task",
                    "task_id": task_id,
                    "task_name": task.name,
                })

    # 创建调整记录；trigger_type 只允许 stage_audit/event 枚举
    raw_trigger = insight_result.get("trigger_type", "")
    trigger_type = raw_trigger if raw_trigger in VALID_TRIGGER_TYPES else ""

    adjustment = Adjustment(
        trigger=insight_result.get("summary", ""),
        trigger_type=trigger_type,
        reason=insight_result.get("adjustment_reason", ""),
        changes=applied_changes,
        approved=insight_result.get("adjustment_type") == "auto",
    )

    profile.add_adjustment(adjustment)
    profile.touch()

    return profile, adjustment


def completed_phase_ids(profile: CareerProfile) -> list[str]:
    """返回所有任务均已完结（完成/跳过）的阶段 id 列表。"""
    done_status = (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
    result = []
    seen: set[str] = set()

    for task in profile.tasks:
        phase_id = task.phase_id
        if not phase_id or phase_id in seen:
            continue
        seen.add(phase_id)
        phase_tasks = [t for t in profile.tasks if t.phase_id == phase_id]
        if all(t.status in done_status for t in phase_tasks):
            result.append(phase_id)

    return result


def format_insight_report(insight_result: dict[str, Any]) -> str:
    """格式化洞察报告。"""
    lines = []

    status = insight_result.get("status", "unknown")
    status_icon = {
        "on_track": "🟢",
        "behind": "🟡",
        "ahead": "🔵",
        "need_adjustment": "🔴",
        "unknown": "⚪",
    }.get(status, "⚪")

    lines.append(f"## {status_icon} 进度洞察")
    lines.append("")

    summary = insight_result.get("summary", "")
    if summary:
        lines.append(f"**{summary}**")
        lines.append("")

    insights = insight_result.get("insights", [])
    if insights:
        lines.append("### 洞察")
        for insight in insights:
            lines.append(f"- {insight}")
        lines.append("")

    if insight_result.get("adjustment_needed"):
        lines.append("### 🔄 调整建议")
        lines.append(f"原因：{insight_result.get('adjustment_reason', '')}")
        lines.append("")

        changes = insight_result.get("changes", [])
        if changes:
            for change in changes:
                lines.append(f"- {change.get('description', change.get('type', ''))}")
            lines.append("")

    user_message = insight_result.get("user_message", "")
    if user_message:
        lines.append(f"---")
        lines.append(f"*{user_message}*")

    return "\n".join(lines)
