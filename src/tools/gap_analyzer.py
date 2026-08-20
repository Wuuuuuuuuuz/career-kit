"""差距分析——SOP 驱动的 RAG 模式。

工作流：
1. 加载 SOP 配置（简历过筛 / 面试通过）
2. 按步骤执行：构建画像 → 检索数据 → 差异分析 → 构建建议
3. LLM 分析 → 结构化 JSON 输出
4. 格式化为可读报告

数据源分层：本地知识库 → LLM 知识（兜底）→ Web Search（TODO）
"""

from __future__ import annotations

import json
from typing import Any

from ..models import CareerProfile
from .sop_executor import execute_sop_with_retrieval

# TODO: 后续接入真实数据源（JobSpy、Boss直聘等）
# TODO: 缓存 LLM 分析结果，避免重复调用
# TODO: Web Search API 接入（Tavily / SerpAPI）


def build_sop_analysis_prompt(profile: CareerProfile) -> tuple[str, dict[str, Any]]:
    """基于 SOP 构建差距分析的完整 prompt。

    执行两个 SOP（简历过筛 + 面试通过），收集中间结果，
    组合成一个完整的分析 prompt。

    Args:
        profile: 用户职业档案

    Returns:
        (prompt_text, sop_metadata) 元组
        - prompt_text: 发给 LLM 的完整 prompt
        - sop_metadata: SOP 执行元数据（中间步骤信息）
    """
    metadata = {"steps_executed": []}

    # === SOP 1: 简历过筛 ===
    resume_sop = execute_sop_with_retrieval(
        "resume_screening",
        user_have=profile.have,
        user_want=profile.want,
        target_jd=profile.target_jd,
    )
    metadata["resume_sop"] = {
        "name": resume_sop["sop_name"],
        "version": resume_sop["sop_version"],
        "steps": [{"id": s["id"], "name": s["name"]} for s in resume_sop["steps"]],
    }

    # === SOP 2: 面试通过 ===
    interview_sop = execute_sop_with_retrieval(
        "interview_prep",
        user_have=profile.have,
        user_want=profile.want,
        target_jd=profile.target_jd,
    )
    metadata["interview_sop"] = {
        "name": interview_sop["sop_name"],
        "version": interview_sop["sop_version"],
        "steps": [{"id": s["id"], "name": s["name"]} for s in interview_sop["steps"]],
    }

    # === 组装最终 prompt ===
    user_want_summary = _extract_want_summary(profile.want)

    prompt_parts = [
        f"你是一个资深的职业规划专家和技术面试官。",
        f"用户的目标是：{user_want_summary}",
        "",
        "你需要从两个核心角度帮助用户：",
        "1. **简历过筛** — 怎么写简历能通过 ATS 和 HR 筛选",
        "2. **面试通过** — 面试会问什么、怎么准备",
        "",
        "## 用户现状（have）",
        json.dumps(profile.have, ensure_ascii=False, indent=2) if profile.have else "（未填写）",
        "",
        "## 用户目标（want）",
        json.dumps(profile.want, ensure_ascii=False, indent=2) if profile.want else "（未填写）",
        "",
    ]

    # JD 信息
    if profile.target_jd:
        prompt_parts.extend([
            "## 参考 JD（仅作补充，不要局限于此）",
            json.dumps(profile.target_jd, ensure_ascii=False, indent=2),
            "",
            "注意：JD 只是表面要求，请基于你的行业经验分析**真正需要的能力**。",
            "",
        ])

    # SOP 中间结果
    prompt_parts.extend([
        "## 分析过程",
        "",
        "### SOP 1: 简历过筛",
    ])
    for step in resume_sop["steps"]:
        prompt_parts.append(f"\n#### {step['name']}")
        if step.get("prompt"):
            prompt_parts.append(step["prompt"])
        if step.get("search_results"):
            prompt_parts.append("\n检索到的数据：")
            for r in step["search_results"]:
                if r.get("content"):
                    prompt_parts.append(f"- [{r['source']}] {r['content'][:500]}")

    prompt_parts.extend(["", "### SOP 2: 面试通过"])
    for step in interview_sop["steps"]:
        prompt_parts.append(f"\n#### {step['name']}")
        if step.get("prompt"):
            prompt_parts.append(step["prompt"])
        if step.get("search_results"):
            prompt_parts.append("\n检索到的数据：")
            for r in step["search_results"]:
                if r.get("content"):
                    prompt_parts.append(f"- [{r['source']}] {r['content'][:500]}")

    # 最终输出格式要求
    prompt_parts.extend(_build_output_format_instructions())

    return "\n".join(prompt_parts), metadata


def _build_output_format_instructions() -> list[str]:
    """构建输出格式要求。"""
    return [
        "",
        "## 输出要求",
        "",
        "请严格输出以下 JSON 格式的差距分析（不要输出其他内容）：",
        "```json",
        json.dumps({
            "match_score": 75,
            "match_level": "strong_match/good_match/partial_match/weak_match",
            "resume_optimization": {
                "ats_keywords": ["ATS 关键词1", "关键词2"],
                "highlight_projects": [
                    {"project": "项目名", "how_to_package": "如何包装", "quantified_result": "量化结果"}
                ],
                "missing_keywords": ["简历中缺少但岗位要求的关键词"],
                "resume_tips": ["简历优化建议1", "建议2"],
                "missing_experiences": [
                    {"experience": "建议补充的经历类型", "how_to_create": "如何创造"}
                ],
            },
            "interview_preparation": {
                "must_prepare": [
                    {"topic": "必考题", "type": "八股/项目深挖/系统设计/行为面/算法", "priority": "high/medium/low", "prepare_advice": "准备建议", "estimated_time": "建议时间"}
                ],
                "project_deep_dive": [
                    {"project": "项目名", "likely_questions": ["问题"], "key_points": ["要点"], "star_story": "STAR 故事框架"}
                ],
                "system_design_topics": [
                    {"topic": "系统设计题", "framework": "答题框架"}
                ],
                "behavioral_questions": [
                    {"question": "行为面试题", "story_template": "故事模板"}
                ],
                "study_plan": {
                    "week_1": ["学习内容"],
                    "week_2": ["学习内容"],
                },
            },
            "strengths": [
                {"area": "优势领域", "description": "描述", "resume_highlight": "简历怎么写", "interview_talk": "面试怎么讲"}
            ],
            "skill_gaps": [
                {"skill": "技能名", "current_level": "当前水平", "required_level": "要求水平", "priority": "high/medium/low", "is_hidden": True, "how_to_improve": "提升建议"}
            ],
            "priority_actions": [
                {"action": "行动项", "timeline": "建议时间", "impact": "对简历/面试的影响", "difficulty": "easy/medium/hard"}
            ],
            "market_context": "市场背景分析",
        }, ensure_ascii=False, indent=4),
        "```",
        "",
        "注意：",
        "- `resume_optimization` 针对简历过筛",
        "- `interview_preparation` 针对面试通过",
        "- `is_hidden` 标记 JD 没写但实际考核的技能",
        "- `study_plan` 是分周学习计划",
    ]


def _extract_want_summary(want: dict[str, Any]) -> str:
    """从 want 中提取目标摘要。"""
    if not want:
        return "（未填写）"

    parts = []
    if want.get("target_role"):
        parts.append(want["target_role"])
    if want.get("target_company"):
        parts.append(f"目标公司：{want['target_company']}")
    if want.get("target_direction"):
        parts.append(f"方向：{want['target_direction']}")

    return "，".join(parts) if parts else json.dumps(want, ensure_ascii=False)


# === 旧接口（向后兼容） ===

# TODO: 旧的 GAP_ANALYSIS_PROMPT 已废弃，由 SOP 驱动替代
# 保留 build_gap_analysis_prompt 作为简单场景的降级方案


def build_gap_analysis_prompt(profile: CareerProfile) -> str:
    """构建差距分析 prompt（简单版本，不走 SOP）。

    对于不需要 SOP 完整流程的场景，使用这个简化版本。
    完整分析请使用 build_sop_analysis_prompt。

    Args:
        profile: 用户职业档案

    Returns:
        prompt 字符串
    """
    prompt, _ = build_sop_analysis_prompt(profile)
    return prompt


def parse_gap_analysis(llm_response: str) -> dict[str, Any]:
    """解析 LLM 输出为结构化差距数据。

    Args:
        llm_response: LLM 的原始输出

    Returns:
        结构化的差距分析 dict
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
            "raw_analysis": llm_response,
            "skill_gaps": [],
            "experience_gaps": [],
            "strengths": [],
            "match_score": 0,
            "priority_actions": [],
            "market_context": "（解析失败，请查看 raw_analysis）",
        }

    # 确保必要字段存在
    result.setdefault("skill_gaps", [])
    result.setdefault("experience_gaps", [])
    result.setdefault("strengths", [])
    result.setdefault("match_score", 0)
    result.setdefault("priority_actions", [])
    result.setdefault("market_context", "")
    result.setdefault("resume_optimization", {})
    result.setdefault("interview_preparation", {})

    return result


def format_gap_report(gap: dict[str, Any]) -> str:
    """格式化差距报告为可读文本。

    Args:
        gap: parse_gap_analysis 返回的结构化数据

    Returns:
        格式化的文本报告
    """
    lines = []

    # 匹配度评分
    score = gap.get("match_score", 0)
    level = gap.get("match_level", "")
    level_text = {
        "strong_match": "强烈匹配 ⭐⭐⭐⭐⭐",
        "good_match": "良好匹配 ⭐⭐⭐⭐",
        "partial_match": "部分匹配 ⭐⭐⭐",
        "weak_match": "匹配度低 ⭐⭐",
    }.get(level, "")

    score_bar = "█" * (score // 5) + "░" * (20 - score // 5)
    lines.append(f"## 匹配度评分：{score}/100 {level_text}")
    lines.append(f"[{score_bar}]")
    lines.append("")

    # === 优势 ===
    strengths = gap.get("strengths", [])
    if strengths:
        lines.append("## ✅ 你的优势")
        for s in strengths:
            lines.append(f"- **{s.get('area', '')}**：{s.get('description', '')}")
            if s.get('resume_highlight'):
                lines.append(f"  - 简历怎么写：{s['resume_highlight']}")
            if s.get('interview_talk'):
                lines.append(f"  - 面试怎么讲：{s['interview_talk']}")
        lines.append("")

    # === 简历优化（简历过筛） ===
    resume_opt = gap.get("resume_optimization", {})
    if resume_opt:
        lines.append("## 📝 简历优化（过筛指南）")
        lines.append("")

        ats_keywords = resume_opt.get("ats_keywords", [])
        if ats_keywords:
            lines.append("### ATS 关键词（简历中必须出现）")
            lines.append("、".join(f"**{k}**" for k in ats_keywords))
            lines.append("")

        missing = resume_opt.get("missing_keywords", [])
        if missing:
            lines.append("### 缺失关键词（简历中需要补充）")
            lines.append("、".join(f"**{k}**" for k in missing))
            lines.append("")

        highlights = resume_opt.get("highlight_projects", [])
        if highlights:
            lines.append("### 项目包装建议")
            for h in highlights:
                lines.append(f"- **{h.get('project', '')}**")
                lines.append(f"  - 包装方式：{h.get('how_to_package', '')}")
                if h.get('quantified_result'):
                    lines.append(f"  - 量化结果：{h['quantified_result']}")
            lines.append("")

        tips = resume_opt.get("resume_tips", [])
        if tips:
            lines.append("### 简历优化建议")
            for t in tips:
                lines.append(f"- {t}")
            lines.append("")

        missing_exp = resume_opt.get("missing_experiences", [])
        if missing_exp:
            lines.append("### 建议补充的经历")
            for e in missing_exp:
                lines.append(f"- **{e.get('experience', '')}**")
                if e.get('how_to_create'):
                    lines.append(f"  - 如何创造：{e['how_to_create']}")
            lines.append("")

    # === 面试准备（面试通过） ===
    interview = gap.get("interview_preparation", {})
    if interview:
        lines.append("## 🎯 面试准备（通关指南）")
        lines.append("")

        must_prepare = interview.get("must_prepare", [])
        if must_prepare:
            lines.append("### 必考题（必须准备）")
            for item in must_prepare:
                priority = item.get('priority', 'medium')
                priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, '⚪')
                time_est = f" ~{item['estimated_time']}" if item.get('estimated_time') else ""
                lines.append(f"- {priority_icon} **{item.get('topic', '')}** [{item.get('type', '')}]{time_est}")
                if item.get('prepare_advice'):
                    lines.append(f"  - 准备建议：{item['prepare_advice']}")
            lines.append("")

        project_deep = interview.get("project_deep_dive", [])
        if project_deep:
            lines.append("### 项目深挖（面试官会追问的项目）")
            for p in project_deep:
                lines.append(f"- **{p.get('project', '')}**")
                if p.get('likely_questions'):
                    lines.append("  - 可能被问：")
                    for q in p['likely_questions']:
                        lines.append(f"    - {q}")
                if p.get('key_points'):
                    lines.append("  - 回答要点：")
                    for k in p['key_points']:
                        lines.append(f"    - {k}")
                if p.get('star_story'):
                    lines.append(f"  - STAR 故事框架：{p['star_story']}")
            lines.append("")

        sys_design = interview.get("system_design_topics", [])
        if sys_design:
            lines.append("### 系统设计题")
            for s in sys_design:
                if isinstance(s, dict):
                    lines.append(f"- **{s.get('topic', '')}**")
                    if s.get('framework'):
                        lines.append(f"  - 框架：{s['framework']}")
                else:
                    lines.append(f"- {s}")
            lines.append("")

        behavioral = interview.get("behavioral_questions", [])
        if behavioral:
            lines.append("### 行为面试题")
            for b in behavioral:
                if isinstance(b, dict):
                    lines.append(f"- **{b.get('question', '')}**")
                    if b.get('story_template'):
                        lines.append(f"  - 故事模板：{b['story_template']}")
                else:
                    lines.append(f"- {b}")
            lines.append("")

        study_plan = interview.get("study_plan", {})
        if study_plan:
            lines.append("### 学习计划")
            for week, items in study_plan.items():
                lines.append(f"- **{week}**：{', '.join(items) if isinstance(items, list) else items}")
            lines.append("")

    # === 技能差距 ===
    skill_gaps = gap.get("skill_gaps", [])
    if skill_gaps:
        lines.append("## 📚 技能差距")

        explicit = [g for g in skill_gaps if not g.get('is_hidden')]
        hidden = [g for g in skill_gaps if g.get('is_hidden')]

        if explicit:
            lines.append("### 显性要求（JD 上写的）")
            for priority in ['high', 'medium', 'low']:
                icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}[priority]
                for g in [g for g in explicit if g.get('priority') == priority]:
                    lines.append(f"- {icon} **{g.get('skill', '')}**：{g.get('current_level', '?')} → {g.get('required_level', '?')}")
                    if g.get('how_to_improve'):
                        lines.append(f"  - 提升建议：{g['how_to_improve']}")

        if hidden:
            lines.append("")
            lines.append("### 隐性要求（JD 没写但实际考核的）")
            for g in hidden:
                priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(g.get('priority'), '⚪')
                lines.append(f"- {priority_icon} **{g.get('skill', '')}**：{g.get('current_level', '?')} → {g.get('required_level', '?')}")
                if g.get('how_to_improve'):
                    lines.append(f"  - 提升建议：{g['how_to_improve']}")
        lines.append("")

    # === 优先行动项 ===
    actions = gap.get("priority_actions", [])
    if actions:
        lines.append("## 🚀 优先行动项")
        for i, a in enumerate(actions, 1):
            lines.append(f"{i}. **{a.get('action', '')}**")
            if a.get('timeline'):
                lines.append(f"   - 时间：{a['timeline']}")
            if a.get('impact'):
                lines.append(f"   - 影响：{a['impact']}")
            if a.get('difficulty'):
                lines.append(f"   - 难度：{a['difficulty']}")
        lines.append("")

    # === 市场背景 ===
    market = gap.get("market_context", "")
    if market:
        lines.append("## 📊 市场背景")
        lines.append(market)
        lines.append("")

    return "\n".join(lines)
