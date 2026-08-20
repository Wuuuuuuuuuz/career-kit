"""进度追踪——签到模式 + 偏差分析 + 自动重排。

借鉴：
- Plan Tracker MCP：签到（进度/时间/阻碍/士气）、偏差分析、节奏比
- Progress-Loop：自适应重排、失败预测
- SkillForge：游戏化激励
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..models import CareerProfile


def parse_checkin(checkin_text: str) -> dict[str, Any]:
    """解析用户的签到/进度汇报。

    支持自然语言输入，提取结构化签到数据。

    Args:
        checkin_text: 用户的进度汇报（自然语言）

    Returns:
        结构化的签到数据
    """
    # 基础签到结构（借鉴 Plan Tracker MCP）
    return {
        "raw_text": checkin_text,
        "timestamp": datetime.now().isoformat(),
        # 以下字段由 LLM 填充
        "completed_tasks": [],      # 完成的任务
        "progress_pct": 0,          # 整体进度百分比
        "time_spent": "",           # 花费时间
        "blockers": [],             # 遇到的阻碍
        "morale": "neutral",        # 士气：high/neutral/low
        "notes": "",                # 备注
    }


def build_checkin_prompt(profile: CareerProfile, checkin_text: str) -> str:
    """构建签到解析的 LLM prompt。

    Args:
        profile: 用户职业档案
        checkin_text: 用户的进度汇报

    Returns:
        prompt 字符串
    """
    roadmap = profile.plan.get("roadmap", profile.plan)
    roadmap_text = json.dumps(roadmap, ensure_ascii=False, indent=2) if roadmap else "（无路线图）"

    # 提取当前进度日志
    progress_log = profile.plan.get("progress_log", [])
    recent_log = progress_log[-5:] if progress_log else []
    log_text = json.dumps(recent_log, ensure_ascii=False, indent=2) if recent_log else "（首次签到）"

    return f"""你是一个执行力教练，负责分析用户的进度汇报。

## 当前路线图
{roadmap_text}

## 近期签到记录
{log_text}

## 用户本次汇报
{checkin_text}

请分析用户的汇报，输出 JSON：
```json
{{
    "completed_tasks": ["完成的任务1", "任务2"],
    "progress_pct": 65,
    "time_spent": "3小时",
    "blockers": ["遇到的阻碍1"],
    "morale": "high|neutral|low",
    "notes": "补充说明",
    "deviation": {{
        "on_track": true,
        "days_ahead_or_behind": 0,
        "reason": "进度正常/落后原因"
    }},
    "next_steps": ["下一步建议1", "建议2"],
    "adjustments": {{
        "needed": false,
        "reason": "",
        "suggested_changes": []
    }}
}}
```

分析要点：
1. 对比路线图，判断用户完成了哪些任务
2. 计算实际进度 vs 计划进度的偏差
3. 如果落后，建议如何调整（压缩/跳过低优先级/延长）
4. 如果遇到阻碍，给出解决建议
5. 根据士气状态调整鼓励方式"""


def parse_checkin_response(llm_response: str) -> dict[str, Any]:
    """解析 LLM 的签到分析结果。

    Args:
        llm_response: LLM 的原始输出

    Returns:
        结构化的签到分析
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
            "completed_tasks": [],
            "progress_pct": 0,
            "blockers": [],
            "morale": "neutral",
            "deviation": {"on_track": True, "days_ahead_or_behind": 0, "reason": "解析失败"},
            "adjustments": {"needed": False},
        }

    # 确保必要字段
    result.setdefault("completed_tasks", [])
    result.setdefault("progress_pct", 0)
    result.setdefault("time_spent", "")
    result.setdefault("blockers", [])
    result.setdefault("morale", "neutral")
    result.setdefault("deviation", {"on_track": True, "days_ahead_or_behind": 0, "reason": ""})
    result.setdefault("next_steps", [])
    result.setdefault("adjustments", {"needed": False, "reason": "", "suggested_changes": []})

    return result


def save_checkin(profile: CareerProfile, checkin_data: dict[str, Any]) -> CareerProfile:
    """保存签到记录到档案。

    Args:
        profile: 用户职业档案
        checkin_data: 签到数据

    Returns:
        更新后的档案
    """
    if "progress_log" not in profile.plan:
        profile.plan["progress_log"] = []

    profile.plan["progress_log"].append({
        "timestamp": datetime.now().isoformat(),
        "completed_tasks": checkin_data.get("completed_tasks", []),
        "progress_pct": checkin_data.get("progress_pct", 0),
        "time_spent": checkin_data.get("time_spent", ""),
        "blockers": checkin_data.get("blockers", []),
        "morale": checkin_data.get("morale", "neutral"),
        "notes": checkin_data.get("notes", ""),
        "deviation": checkin_data.get("deviation", {}),
    })

    # 更新整体进度
    profile.plan["current_progress"] = checkin_data.get("progress_pct", 0)

    profile.touch()
    return profile


def format_checkin_report(checkin_data: dict[str, Any]) -> str:
    """格式化签到报告。

    Args:
        checkin_data: parse_checkin_response 返回的数据

    Returns:
        格式化的 Markdown 文本
    """
    lines = []

    # 进度概览
    pct = checkin_data.get("progress_pct", 0)
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    lines.append(f"## 📊 进度签到报告")
    lines.append(f"整体进度：{pct}% [{bar}]")
    lines.append("")

    # 完成的任务
    completed = checkin_data.get("completed_tasks", [])
    if completed:
        lines.append("### ✅ 已完成")
        for t in completed:
            lines.append(f"- {t}")
        lines.append("")

    # 花费时间
    time_spent = checkin_data.get("time_spent", "")
    if time_spent:
        lines.append(f"⏱️ 花费时间：{time_spent}")
        lines.append("")

    # 偏差分析
    deviation = checkin_data.get("deviation", {})
    if deviation:
        on_track = deviation.get("on_track", True)
        days = deviation.get("days_ahead_or_behind", 0)
        reason = deviation.get("reason", "")

        if on_track and days >= 0:
            lines.append("### 🎯 进度状态：正常")
            if days > 0:
                lines.append(f"提前 {days} 天")
        elif on_track and days < 0:
            lines.append(f"### ⚠️ 进度状态：落后 {abs(days)} 天")
        else:
            lines.append(f"### 🔴 进度状态：偏离计划")
        if reason:
            lines.append(f"原因：{reason}")
        lines.append("")

    # 阻碍
    blockers = checkin_data.get("blockers", [])
    if blockers:
        lines.append("### 🚧 遇到阻碍")
        for b in blockers:
            lines.append(f"- {b}")
        lines.append("")

    # 士气
    morale = checkin_data.get("morale", "neutral")
    morale_icon = {"high": "💪", "neutral": "😐", "low": "😔"}.get(morale, "😐")
    morale_text = {"high": "状态很好", "neutral": "正常", "low": "需要调整"}.get(morale, "正常")
    lines.append(f"士气：{morale_icon} {morale_text}")
    lines.append("")

    # 下一步
    next_steps = checkin_data.get("next_steps", [])
    if next_steps:
        lines.append("### 📋 下一步")
        for s in next_steps:
            lines.append(f"- {s}")
        lines.append("")

    # 调整建议
    adjustments = checkin_data.get("adjustments", {})
    if adjustments.get("needed"):
        lines.append("### 🔄 计划调整建议")
        lines.append(f"原因：{adjustments.get('reason', '')}")
        for change in adjustments.get("suggested_changes", []):
            lines.append(f"- {change}")
        lines.append("")

    return "\n".join(lines)


def format_progress_overview(profile: CareerProfile) -> str:
    """格式化整体进度概览。

    Args:
        profile: 用户职业档案

    Returns:
        格式化的进度概览
    """
    lines = []
    progress_log = profile.plan.get("progress_log", [])
    current_pct = profile.plan.get("current_progress", 0)

    bar = "█" * (current_pct // 5) + "░" * (20 - current_pct // 5)
    lines.append(f"## 📊 整体进度：{current_pct}% [{bar}]")
    lines.append(f"共签到 {len(progress_log)} 次")
    lines.append("")

    if progress_log:
        lines.append("### 近期签到记录")
        for entry in progress_log[-5:]:
            ts = entry.get("timestamp", "")[:10]
            pct = entry.get("progress_pct", 0)
            morale = entry.get("morale", "neutral")
            morale_icon = {"high": "💪", "neutral": "😐", "low": "😔"}.get(morale, "😐")
            completed = len(entry.get("completed_tasks", []))
            lines.append(f"- {ts}：{pct}% {morale_icon}（完成 {completed} 项）")
        lines.append("")

    # 里程碑状态
    roadmap = profile.plan.get("roadmap", {})
    phases = roadmap.get("phases", [])
    if phases:
        lines.append("### 里程碑进度")
        for phase in phases:
            lines.append(f"- **{phase.get('name', '')}** [{phase.get('type', '')}]")
            for ms in phase.get("milestones", []):
                lines.append(f"  - {ms.get('name', '')}：{ms.get('duration', '')}")
        lines.append("")

    return "\n".join(lines)
