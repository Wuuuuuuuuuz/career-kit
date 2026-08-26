"""路线图解析与格式化——将 LLM 输出解析为结构化路线图并格式化展示。

任务 schema 与 sop/roadmap.yaml 一致：{name, description, priority}。
阶段 id 由本模块规范化（phase_N），是任务生成与阶段审计的唯一来源。
产品不规划时间：路线图不含时长字段，只定义顺序与完成标准。
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

    # 兼容 markdown code block 包裹
    if "```json" in llm_response:
        start = llm_response.index("```json") + 7
        end = llm_response.index("```", start)
        json_str = llm_response[start:end].strip()
    elif "```" in llm_response:
        start = llm_response.index("```") + 3
        end = ll_response.index("```", start)
        json_str = ll_response[start:end].strip()

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError:
        return {
            "raw_roadmap": llm_response,
            "roadmap": {
                "strategy_summary": "（解析失败，请查看 raw_roadmap）",
                "phases": [],
            },
        }

    # 确保结构完整
    if "roadmap" not in result:
        result = {"roadmap": result}

    roadmap = result["roadmap"]
    roadmap.pop("total_duration", None)  # 产品不规划时间
    roadmap.setdefault("strategy_summary", "")
    roadmap.setdefault("phases", [])

    # 确保每个 phase 有必要字段；id 统一为 phase_N，作为任务与审计的关联键
    for idx, phase in enumerate(roadmap["phases"]):
        phase["id"] = f"phase_{idx + 1}"
        phase.setdefault("type", "learn")
        phase.setdefault("name", "")
        phase.setdefault("goal", "")
        phase.setdefault("kpi", {"metric": "", "target": "", "evidence": ""})
        phase.setdefault("resume_value", "")
        phase.setdefault("milestones", [])

        # jd 三件套（知识光谱）：
        # company/rationale 是公开常识可自由写；jd 是时效事实，有真实数据才填。
        # jd_status 默认按类型推断：intern 无标注视为待导入占位，其余无需 JD。
        phase.setdefault("company", "")
        phase.setdefault("rationale", "")
        phase.setdefault("jd", None)
        phase.setdefault("confirmed", False)
        if "jd_status" not in phase:
            phase["jd_status"] = "pending_user_import" if phase["type"] == "intern" else "not_required"

        for ms_idx, ms in enumerate(phase["milestones"]):
            ms["id"] = f"phase_{idx + 1}_ms_{ms_idx + 1}"
            ms.setdefault("name", "")
            ms.setdefault("tasks", [])
            ms.setdefault("deliverable", "")
            ms.setdefault("done_criteria", "")

            for task in ms["tasks"]:
                task.setdefault("name", "")
                task.setdefault("description", "")
                task.setdefault("priority", "medium")

    return result


def format_roadmap(roadmap_data: dict[str, Any]) -> str:
    """格式化路线图为可读文本。"""
    roadmap = roadmap_data.get("roadmap", roadmap_data)
    lines = []

    strategy = roadmap.get("strategy_summary", "")

    lines.append("## 路线图")
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

        lines.append(f"### {type_icon} {phase.get('name', '')} [{phase_type}]（{phase.get('id', '')}）")
        lines.append(f"**目标**：{phase.get('goal', '')}")
        lines.append("")

        # jd 三件套展示：公司名（常识）+ 依据状态（has_jd/占位/免JD）
        company = phase.get("company", "")
        if company:
            rationale = phase.get("rationale", "")
            line = f"**目标公司**：{company}"
            if rationale:
                line += f"（{rationale}）"
            lines.append(line)

        jd_status = phase.get("jd_status", "not_required")
        confirmed = phase.get("confirmed", False)
        if jd_status == "has_jd":
            jd = phase.get("jd")
            if jd:
                if isinstance(jd, dict):
                    jd_parts = [f"{k}：{v}" for k, v in jd.items() if v]
                    lines.append(f"📄 **JD 依据**：{'；'.join(jd_parts)[:300]}")
                else:
                    lines.append(f"📄 **JD 依据**：{str(jd)[:300]}")
        elif jd_status == "pending_user_import":
            mark = "（已确认占位）" if confirmed else "（待用户确认）"
            lines.append(f"⏳ **待导入真实 JD 后细化**{mark}——当前只有公司名，无岗位要求细节")
        lines.append("")

        kpi = phase.get("kpi", {})
        if isinstance(kpi, dict) and kpi.get("metric"):
            lines.append(f"**KPI**：{kpi['metric']} → 目标：{kpi.get('target', '?')}")
            if kpi.get("evidence"):
                lines.append(f"**验证方式**：{kpi['evidence']}")
            lines.append("")

        resume_val = phase.get("resume_value", "")
        if resume_val:
            lines.append(f"**简历价值**：{resume_val}")
            lines.append("")

        for ms in phase.get("milestones", []):
            done_criteria = ms.get("done_criteria", "")
            header = f"**{ms.get('name', '')}**"
            if done_criteria:
                header += f"—完成标准：{done_criteria}"
            lines.append(header)

            for t in ms.get("tasks", []):
                priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t.get("priority", "medium"), "⚪")
                desc = f"—{t['description']}" if t.get("description") else ""
                lines.append(f"  - {priority_icon} {t.get('name', '')}{desc}")

            if ms.get("deliverable"):
                lines.append(f"  📦 交付物：{ms['deliverable']}")
            lines.append("")

    return "\n".join(lines)
