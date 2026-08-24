"""路线图解析与格式化——将 LLM 输出解析为结构化路线图并格式化展示。

parse_roadmap: 将 LLM 输出解析为结构化路线图数据
format_roadmap: 将结构化数据格式化为可读文本
"""

from __future__ import annotations

import json
from typing import Any


def parse_roadmap(llm_response: str) -> dict[str, Any]:
    """解析 LLM 输出为结构化路线图。

    Args:
        llm_response: LLM 的原始输出

    Returns:
        结构化的路线图 dict，可直接写入 profile.plan
    """
    json_str = llm_response

    # 从 markdown code block 中提取
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
            "raw_roadmap": llm_response,
            "roadmap": {
                "total_duration": "",
                "strategy_summary": "（解析失败，请查看 raw_roadmap）",
                "phases": [],
            },
        }

    # 确保结构完整
    if "roadmap" not in result:
        result = {"roadmap": result}

    roadmap = result["roadmap"]
    roadmap.setdefault("total_duration", "")
    roadmap.setdefault("strategy_summary", "")
    roadmap.setdefault("phases", [])

    # 确保每个 phase 有必要的字段
    for phase in roadmap["phases"]:
        phase.setdefault("id", "")
        phase.setdefault("type", "learn")
        phase.setdefault("name", "")
        phase.setdefault("duration", "")
        phase.setdefault("goal", "")
        phase.setdefault("kpi", {"metric": "", "target": "", "evidence": ""})
        phase.setdefault("resume_value", "")
        phase.setdefault("milestones", [])

        # 确保每个 milestone 有必要的字段
        for ms in phase["milestones"]:
            ms.setdefault("id", "")
            ms.setdefault("name", "")
            ms.setdefault("duration", "")
            ms.setdefault("tasks", [])
            ms.setdefault("deliverable", "")
            ms.setdefault("done_criteria", "")

            # 确保每个 task 有必要的字段
            for task in ms["tasks"]:
                task.setdefault("task", "")
                task.setdefault("time", "")
                task.setdefault("priority", "medium")

    return result


def format_roadmap(roadmap_data: dict[str, Any]) -> str:
    """格式化路线图为可读文本。

    Args:
        roadmap_data: parse_roadmap 返回的结构化数据

    Returns:
        格式化的 Markdown 文本
    """
    roadmap = roadmap_data.get("roadmap", roadmap_data)
    lines = []

    total = roadmap.get("total_duration", "")
    strategy = roadmap.get("strategy_summary", "")

    lines.append(f"## 路线图（{total}）")
    lines.append("")
    if strategy:
        lines.append(strategy)
        lines.append("")

    phases = roadmap.get("phases", [])
    for phase in phases:
        phase_type = phase.get("type", "")
        type_icon = {
            "learn": "📚",
            "project": "🛠️",
            "intern": "💼",
            "research": "🔬",
        }.get(phase_type, "📋")

        lines.append(f"### {type_icon} Phase: {phase.get('name', '')} [{phase_type}] {phase.get('duration', '')}")
        lines.append(f"**目标**：{phase.get('goal', '')}")
        lines.append("")

        # KPI
        kpi = phase.get("kpi", {})
        if kpi.get("metric"):
            lines.append(f"**KPI**：{kpi['metric']} → 目标：{kpi.get('target', '?')}")
            if kpi.get("evidence"):
                lines.append(f"**验证方式**：{kpi['evidence']}")
            lines.append("")

        # 简历价值
        resume_val = phase.get("resume_value", "")
        if resume_val:
            lines.append(f"**简历价值**：{resume_val}")
            lines.append("")

        # 里程碑
        milestones = phase.get("milestones", [])
        for ms in milestones:
            lines.append(f"**{ms.get('name', '')}**（{ms.get('duration', '')}）")

            # 任务列表
            tasks = ms.get("tasks", [])
            for t in tasks:
                priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t.get("priority", "medium"), "⚪")
                lines.append(f"  - {priority_icon} {t.get('task', '')} [{t.get('time', '')}]")

            # 交付物和完成标准
            if ms.get("deliverable"):
                lines.append(f"  📦 交付物：{ms['deliverable']}")
            if ms.get("done_criteria"):
                lines.append(f"  ✅ 完成标准：{ms['done_criteria']}")
            lines.append("")

    return "\n".join(lines)
