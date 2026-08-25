"""洞察引擎——进度检查、阶段审计、调整建议。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..models import (
    Adjustment,
    CareerProfile,
    Task,
    TaskStatus,
)


def build_insight_prompt(
    profile: CareerProfile,
    trigger_type: str = "proactive",
    event_description: str = "",
) -> str:
    """构建洞察分析的 LLM prompt。

    Args:
        profile: 用户职业档案
        trigger_type: 触发类型（stage_audit, event, proactive）
        event_description: 事件描述（当 trigger_type 为 event 时）

    Returns:
        prompt 字符串
    """
    # 任务统计
    total = len(profile.tasks)
    completed = len([t for t in profile.tasks if t.status == TaskStatus.COMPLETED])
    overdue = [t for t in profile.tasks if t.is_overdue()]

    # 超期任务详情
    overdue_text = ""
    if overdue:
        overdue_lines = []
        for t in overdue:
            days = t.days_overdue()
            overdue_lines.append(f"- {t.name}（超期 {days:.1f} 天）")
        overdue_text = "\n".join(overdue_lines)

    # 路线图
    roadmap = profile.plan.get("roadmap", profile.plan)
    roadmap_text = json.dumps(roadmap, ensure_ascii=False, indent=2) if roadmap else "（无路线图）"

    # 近期打卡
    recent_checkins = profile.checkins[-5:] if profile.checkins else []
    checkin_text = json.dumps(
        [c.model_dump() for c in recent_checkins],
        ensure_ascii=False,
        indent=2,
    ) if recent_checkins else "（无打卡记录）"

    # 触发上下文
    trigger_context = ""
    if trigger_type == "stage_audit":
        trigger_context = "用户刚刚完成了一个阶段，请评估是否需要调整后续计划。"
    elif trigger_type == "event":
        trigger_context = f"用户报告了一个事件：{event_description}。请评估是否需要调整目标或计划。"
    else:
        trigger_context = "请检查用户进度，判断是否需要调整。"

    return f"""你是一个职业教练，负责分析用户的进度并提出调整建议。

## 当前档案
- 目标：{profile.want.get('target_role', '未设定')}
- 进度：{completed}/{total} 个任务已完成

## 超期任务
{overdue_text or "无"}

## 路线图
{roadmap_text}

## 近期打卡
{checkin_text}

## 触发原因
{trigger_context}

请分析用户进度，输出 JSON：
```json
{{
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
            "type": "compress_task|add_task|remove_task|modify_task|add_phase",
            "task_id": "task_001",
            "description": "具体调整内容",
            "details": {{}}
        }}
    ],
    "user_message": "给用户的消息（鼓励/建议/警告）"
}}
```

分析要点：
1. 对比计划进度 vs 实际进度
2. 如果落后，建议压缩哪些任务（低优先级优先）
3. 如果提前，建议添加什么深度任务
4. 如果用户报告事件，评估目标是否需要调整
5. 给出鼓励或建议"""


def parse_insight_response(llm_response: str) -> dict[str, Any]:
    """解析 LLM 的洞察分析结果。

    Args:
        llm_response: LLM 的原始输出

    Returns:
        结构化的洞察分析
    """
    json_str = llm_response

    if "```json" in llm_response:
        start = llm_response.index("```json") + 7
        end = llm_response.index("```", start)
        json_str = llm_response[start:end].strip()
    elif "```" in llm_response:
        start = llm_response.index("```") + 3
        end = llm_response.index("```", start)
        json_str = llm_response[start:end].strip()

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError:
        return {
            "raw_response": llm_response,
            "status": "unknown",
            "summary": "解析失败",
            "insights": [],
            "adjustment_needed": False,
            "changes": [],
            "user_message": "",
        }

    # 确保必要字段
    result.setdefault("status", "unknown")
    result.setdefault("summary", "")
    result.setdefault("insights", [])
    result.setdefault("adjustment_needed", False)
    result.setdefault("adjustment_type", "auto")
    result.setdefault("adjustment_reason", "")
    result.setdefault("changes", [])
    result.setdefault("user_message", "")

    return result


def apply_adjustment(
    profile: CareerProfile,
    insight_result: dict[str, Any],
) -> tuple[CareerProfile, Adjustment]:
    """应用调整到档案。

    Args:
        profile: 用户职业档案
        insight_result: 洞察分析结果

    Returns:
        (更新后的档案, 调整记录)
    """
    changes = insight_result.get("changes", [])
    applied_changes = []

    for change in changes:
        change_type = change.get("type")
        task_id = change.get("task_id")

        if change_type == "compress_task" and task_id:
            task = profile.get_task(task_id)
            if task:
                details = change.get("details", {})
                old_days = task.estimated_days
                new_days = details.get("new_days", old_days * 0.75)
                task.estimated_days = round(new_days, 1)
                applied_changes.append({
                    "type": "compress_task",
                    "task_id": task_id,
                    "task_name": task.name,
                    "old_days": old_days,
                    "new_days": task.estimated_days,
                })

        elif change_type == "add_task":
            details = change.get("details", {})
            new_task = Task(
                id=f"task_{len(profile.tasks) + 1:03d}",
                name=details.get("name", change.get("description", "")),
                description=details.get("description", ""),
                phase_id=details.get("phase_id", ""),
                milestone_id=details.get("milestone_id", ""),
                estimated_days=details.get("estimated_days", 1),
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

    # 创建调整记录
    adjustment = Adjustment(
        trigger=insight_result.get("summary", ""),
        trigger_type=insight_result.get("status", "proactive"),
        reason=insight_result.get("adjustment_reason", ""),
        changes=applied_changes,
        approved=insight_result.get("adjustment_type") == "auto",
    )

    profile.add_adjustment(adjustment)
    profile.touch()

    return profile, adjustment


def check_stage_completion(profile: CareerProfile) -> bool:
    """检查阶段是否完成。

    Args:
        profile: 用户职业档案

    Returns:
        是否有阶段完成
    """
    roadmap = profile.plan.get("roadmap", profile.plan)
    phases = roadmap.get("phases", [])

    for phase in phases:
        phase_id = phase.get("id", "")
        phase_tasks = [t for t in profile.tasks if t.phase_id == phase_id]

        if not phase_tasks:
            continue

        all_completed = all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
            for t in phase_tasks
        )

        if all_completed:
            return True

    return False


def format_insight_report(insight_result: dict[str, Any]) -> str:
    """格式化洞察报告。

    Args:
        insight_result: 洞察分析结果

    Returns:
        格式化的 Markdown 文本
    """
    lines = []

    # 状态
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

    # 总结
    summary = insight_result.get("summary", "")
    if summary:
        lines.append(f"**{summary}**")
        lines.append("")

    # 洞察
    insights = insight_result.get("insights", [])
    if insights:
        lines.append("### 洞察")
        for insight in insights:
            lines.append(f"- {insight}")
        lines.append("")

    # 调整建议
    if insight_result.get("adjustment_needed"):
        lines.append("### 🔄 调整建议")
        lines.append(f"原因：{insight_result.get('adjustment_reason', '')}")
        lines.append("")

        changes = insight_result.get("changes", [])
        if changes:
            for change in changes:
                lines.append(f"- {change.get('description', change.get('type', ''))}")
            lines.append("")

    # 用户消息
    user_message = insight_result.get("user_message", "")
    if user_message:
        lines.append(f"---")
        lines.append(f"*{user_message}*")

    return "\n".join(lines)
