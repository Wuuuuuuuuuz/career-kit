"""路线图生成——SOP 驱动，基于差距分析生成分阶段职业路线图。

宏观：分阶段（learn/project/intern/research），每阶段有量化 KPI
微观：落到每一天的任务，最终产出日程表
"""

from __future__ import annotations

import json
from typing import Any

from ..models import CareerProfile
from .sop_executor import execute_sop


def build_roadmap_prompt(profile: CareerProfile) -> tuple[str, dict[str, Any]]:
    """构建路线图生成的 LLM prompt。

    Args:
        profile: 用户职业档案（必须已有 gap 数据）

    Returns:
        (prompt_text, metadata) 元组
    """
    metadata = {"steps_executed": []}

    # 构建差距分析摘要
    gap_summary = _build_gap_summary(profile.gap)

    # 执行路线图 SOP
    sop_result = execute_sop(
        "roadmap",
        user_have=profile.have,
        user_want=profile.want,
    )

    # 将 gap_summary 注入上下文
    context = sop_result["context"]
    context["gap_summary"] = gap_summary

    metadata["roadmap_sop"] = {
        "name": sop_result["sop_name"],
        "version": sop_result["sop_version"],
        "steps": [{"id": s["id"], "name": s["name"]} for s in sop_result["steps"]],
    }

    # 重新构建 prompt（因为 execute_sop 不会用到 gap_summary）
    prompt_parts = []
    for step in sop_result["steps"]:
        if step.get("prompt"):
            # 替换 gap_summary 变量
            prompt = step["prompt"]
            if "{gap_summary}" in prompt:
                prompt = prompt.replace("{gap_summary}", gap_summary)
            prompt_parts.append(f"### {step['name']}\n\n{prompt}")

    return "\n\n".join(prompt_parts), metadata


def _build_gap_summary(gap: dict[str, Any]) -> str:
    """从差距分析中提取摘要，作为路线图的输入。"""
    if not gap:
        return "（未完成差距分析）"

    parts = []

    # 匹配度
    score = gap.get("match_score", 0)
    level = gap.get("match_level", "")
    parts.append(f"匹配度：{score}/100 ({level})")

    # 技能差距
    skill_gaps = gap.get("skill_gaps", [])
    if skill_gaps:
        parts.append("\n### 技能差距")
        for g in skill_gaps:
            hidden = "（隐性）" if g.get("is_hidden") else ""
            parts.append(f"- {g.get('skill', '')}{hidden}：{g.get('current_level', '?')} → {g.get('required_level', '?')} [优先级: {g.get('priority', '?')}]")
            if g.get("how_to_improve"):
                parts.append(f"  提升建议：{g['how_to_improve']}")

    # 优先行动项
    actions = gap.get("priority_actions", [])
    if actions:
        parts.append("\n### 优先行动项")
        for a in actions:
            parts.append(f"- {a.get('action', '')} [时间: {a.get('timeline', '?')}, 影响: {a.get('impact', '?')}, 难度: {a.get('difficulty', '?')}]")

    # 需要补充的经历
    missing_exp = gap.get("resume_optimization", {}).get("missing_experiences", [])
    if missing_exp:
        parts.append("\n### 需要补充的经历")
        for e in missing_exp:
            parts.append(f"- {e.get('experience', '')}：{e.get('how_to_create', '')}")

    # 面试准备
    interview = gap.get("interview_preparation", {})
    study_plan = interview.get("study_plan", {})
    if study_plan:
        parts.append("\n### 面试学习计划")
        for week, items in study_plan.items():
            if isinstance(items, list):
                parts.append(f"- {week}：{', '.join(items)}")

    return "\n".join(parts)


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
