"""差距分析——格式化报告。

format_gap_report: 将结构化差距数据格式化为可读报告
（解析由 server 层的 _parse_json_param 统一完成）
"""

from __future__ import annotations

from typing import Any


def format_gap_report(gap: dict[str, Any]) -> str:
    """格式化差距报告为可读文本。

    对 LLM 退化的字符串条目做兼容渲染，不抛异常。

    Args:
        gap: 结构化差距数据（save_gap_analysis 的入参）

    Returns:
        格式化的文本报告
    """
    lines = []

    # 匹配度评分（容忍 LLM 给出非数字类型）
    raw_score = gap.get("match_score", 0)
    try:
        score = int(raw_score)
        score = max(0, min(100, score))
    except (TypeError, ValueError):
        score = None

    level = gap.get("match_level", "")
    level_text = {
        "strong_match": "强烈匹配",
        "good_match": "良好匹配",
        "partial_match": "部分匹配",
        "weak_match": "匹配度低",
    }.get(level, "")

    if score is None:
        lines.append(f"## 匹配度评分：{raw_score!r} {level_text}")
    else:
        score_bar = "█" * (score // 5) + "░" * (20 - score // 5)
        lines.append(f"## 匹配度评分：{score}/100 {level_text}")
        lines.append(f"[{score_bar}]")
    lines.append("")

    # === 优势 ===
    strengths = gap.get("strengths", [])
    if strengths:
        lines.append("## 你的优势")
        for s in strengths:
            if isinstance(s, dict):
                lines.append(f"- **{s.get('area', '')}**：{s.get('description', '')}")
                if s.get('resume_highlight'):
                    lines.append(f"  - 简历怎么写：{s['resume_highlight']}")
                if s.get('interview_talk'):
                    lines.append(f"  - 面试怎么讲：{s['interview_talk']}")
            else:
                lines.append(f"- {s}")
        lines.append("")

    # === 简历优化（简历过筛） ===
    resume_opt = gap.get("resume_optimization", {})
    if resume_opt:
        lines.append("## 简历优化（过筛指南）")
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
        lines.append("## 面试准备（通关指南）")
        lines.append("")

        must_prepare = interview.get("must_prepare", [])
        if must_prepare:
            lines.append("### 必考题（必须准备）")
            for item in must_prepare:
                priority = item.get('priority', 'medium')
                priority_icon = {"high": "[高]", "medium": "[中]", "low": "[低]"}.get(priority, '[中]')
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
        lines.append("## 技能差距")

        # 兼容字符串条目（LLM 输出退化时）
        dict_gaps = [g for g in skill_gaps if isinstance(g, dict)]
        str_gaps = [g for g in skill_gaps if not isinstance(g, dict)]

        explicit = [g for g in dict_gaps if not g.get('is_hidden')]
        hidden = [g for g in dict_gaps if g.get('is_hidden')]

        if explicit:
            lines.append("### 显性要求（JD 上写的）")
            for priority in ['high', 'medium', 'low']:
                icon = {"high": "[高]", "medium": "[中]", "low": "[低]"}[priority]
                for g in [g for g in explicit if g.get('priority') == priority]:
                    lines.append(f"- {icon} **{g.get('skill', '')}**：{g.get('current_level', '?')} → {g.get('required_level', g.get('target_level', '?'))}")
                    if g.get('how_to_improve'):
                        lines.append(f"  - 提升建议：{g['how_to_improve']}")

        if hidden:
            lines.append("")
            lines.append("### 隐性要求（JD 没写但实际考核的）")
            for g in hidden:
                priority_icon = {"high": "[高]", "medium": "[中]", "low": "[低]"}.get(g.get('priority'), '[中]')
                lines.append(f"- {priority_icon} **{g.get('skill', '')}**：{g.get('current_level', '?')} → {g.get('required_level', g.get('target_level', '?'))}")
                if g.get('how_to_improve'):
                    lines.append(f"  - 提升建议：{g['how_to_improve']}")

        for s in str_gaps:
            lines.append(f"- {s}")
        lines.append("")

    # === 优先行动项 ===
    actions = gap.get("priority_actions", [])
    if actions:
        lines.append("## 优先行动项")
        for i, a in enumerate(actions, 1):
            if isinstance(a, dict):
                lines.append(f"{i}. **{a.get('action', a.get('description', ''))}**")
                if a.get('timeline'):
                    lines.append(f"   - 时间：{a['timeline']}")
                if a.get('impact'):
                    lines.append(f"   - 影响：{a['impact']}")
                if a.get('difficulty'):
                    lines.append(f"   - 难度：{a['difficulty']}")
            else:
                lines.append(f"{i}. **{a}**")
        lines.append("")

    # === 市场背景 ===
    market = gap.get("market_context", "")
    if market:
        lines.append("## 市场背景")
        lines.append(market)
        lines.append("")

    return "\n".join(lines)
