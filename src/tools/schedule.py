"""日程解析、格式化与导出——将 LLM 输出解析为结构化日程表并格式化展示。

借鉴：
- Syllabus-to-Study-Plan MCP：间隔复习模式、多格式导出
- TaskFlow AI：自然语言->结构化日计划
- AI-Daily-Planner：时间块排程

estimate_available_time: 估算用户可用学习时间
parse_schedule: 将 LLM 输出解析为结构化日程数据
format_schedule: 将结构化数据格式化为可读文本
generate_ics: 生成 ICS 日历文件
"""

from __future__ import annotations

import json
from typing import Any

from ..models import CareerProfile


def _scope_description(scope: str) -> str:
    """将 scope 转为可读描述。"""
    descriptions = {
        "today": "今天",
        "this_week": "本周（7天）",
        "this_month": "本月（30天）",
    }
    return descriptions.get(scope, scope)


def _estimate_available_time(profile: CareerProfile) -> str:
    """估算用户可用时间。"""
    # 从 want 中提取时间信息
    want = profile.want
    have = profile.have

    parts = []

    # 检查是否在职
    status = have.get("status", "") or have.get("current_status", "")
    if "在职" in str(status) or "工作" in str(status):
        parts.append("在职状态，工作日可用学习时间约 2-3 小时/天，周末约 6-8 小时/天")
    elif "在校" in str(status) or "学生" in str(status):
        parts.append("在校状态，工作日可用学习时间约 4-6 小时/天，周末约 8-10 小时/天")
    else:
        parts.append("全职准备，每天可用学习时间约 8-10 小时")

    # 检查 deadline
    deadline = want.get("deadline", "") or want.get("timeline", "")
    if deadline:
        parts.append(f"目标时间线：{deadline}")

    return "；".join(parts) if parts else "每天可用 6-8 小时"


def parse_schedule(llm_response: str) -> dict[str, Any]:
    """解析 LLM 输出为结构化日程表。

    Args:
        llm_response: LLM 的原始输出

    Returns:
        结构化的日程 dict
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
            "raw_schedule": llm_response,
            "schedule": {
                "total_days": 0,
                "daily_plans": [],
            },
        }

    if "schedule" not in result:
        result = {"schedule": result}

    schedule = result["schedule"]
    schedule.setdefault("total_days", 0)
    schedule.setdefault("daily_plans", [])

    for day in schedule["daily_plans"]:
        day.setdefault("day", 0)
        day.setdefault("date", "")
        day.setdefault("theme", "")
        day.setdefault("blocks", [])
        day.setdefault("total_hours", 0)
        day.setdefault("notes", "")

        for block in day["blocks"]:
            block.setdefault("time", "")
            block.setdefault("task", "")
            block.setdefault("type", "learn")
            block.setdefault("priority", "medium")

    return result


def format_schedule(schedule_data: dict[str, Any], scope: str = "this_week") -> str:
    """格式化日程表为可读文本。

    Args:
        schedule_data: parse_schedule 返回的结构化数据
        scope: 范围

    Returns:
        格式化的 Markdown 文本
    """
    schedule = schedule_data.get("schedule", schedule_data)
    lines = []

    total_days = schedule.get("total_days", 0)
    lines.append(f"## 📅 日程表（{_scope_description(scope)}）")
    lines.append(f"共 {total_days} 天")
    lines.append("")

    type_icons = {
        "learn": "📚",
        "practice": "✏️",
        "review": "🔄",
        "project": "🛠️",
    }

    daily_plans = schedule.get("daily_plans", [])
    for day in daily_plans:
        day_num = day.get("day", "?")
        date = day.get("date", "")
        theme = day.get("theme", "")
        total_hours = day.get("total_hours", 0)

        date_str = f" ({date})" if date else ""
        lines.append(f"### Day {day_num}{date_str}：{theme}")
        lines.append(f"⏱️ 预计 {total_hours} 小时")
        lines.append("")

        blocks = day.get("blocks", [])
        for block in blocks:
            icon = type_icons.get(block.get("type", ""), "📋")
            priority = block.get("priority", "medium")
            priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
            lines.append(f"  {icon} {block.get('time', '')} — {block.get('task', '')} {priority_icon}")

        notes = day.get("notes", "")
        if notes:
            lines.append(f"  💡 {notes}")
        lines.append("")

    return "\n".join(lines)


def generate_ics(schedule_data: dict[str, Any], start_date: str = "") -> str:
    """生成 ICS 日历文件内容。

    借鉴 Syllabus-to-Study-Plan MCP 的 ICS 导出功能。

    Args:
        schedule_data: parse_schedule 返回的结构化数据
        start_date: 起始日期（YYYY-MM-DD），为空则从 Day 1 开始

    Returns:
        ICS 格式字符串
    """
    from datetime import datetime, timedelta

    schedule = schedule_data.get("schedule", schedule_data)
    daily_plans = schedule.get("daily_plans", [])

    if not start_date:
        start = datetime.now()
    else:
        start = datetime.strptime(start_date, "%Y-%m-%d")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Career Kit//Schedule//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    event_id = 0
    for day in daily_plans:
        day_idx = day.get("day", 1) - 1
        current_date = start + timedelta(days=day_idx)
        date_str = current_date.strftime("%Y%m%d")

        for block in day.get("blocks", []):
            event_id += 1
            time_str = block.get("time", "")

            # 解析时间块
            if "-" in time_str:
                parts = time_str.split("-")
                start_time = parts[0].strip().replace(":", "")
                end_time = parts[1].strip().replace(":", "")
            else:
                start_time = "0900"
                end_time = "1100"

            task = block.get("task", "学习任务")
            block_type = block.get("type", "learn")
            type_names = {"learn": "学习", "practice": "练习", "review": "复习", "project": "项目"}
            type_name = type_names.get(block_type, "任务")

            lines.extend([
                "BEGIN:VEVENT",
                f"DTSTART:{date_str}T{start_time}00",
                f"DTEND:{date_str}T{end_time}00",
                f"SUMMARY:[{type_name}] {task}",
                f"DESCRIPTION:Career Kit 自动生成 - {day.get('theme', '')}",
                f"UID:career-kit-{event_id}@career-kit",
                "END:VEVENT",
            ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)
