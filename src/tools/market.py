"""市场搜索——岗位、薪资、面试信息。

通过 DataRouter 路由搜索请求：
1. 本地知识库（dev/knowledge/market/）
2. LLM 知识（兜底）
3. Web Search API（TODO: 后续接入）
"""

from __future__ import annotations

import json
from typing import Any

from .data_source import DataRouter


def search_market_data(query: str) -> dict[str, Any]:
    """搜索市场数据。

    Args:
        query: 搜索内容（岗位名称、公司、薪资、面试经验等）

    Returns:
        搜索结果 dict
    """
    router = DataRouter()

    # 推断搜索类型
    search_type = _infer_search_type(query)

    # 本地搜索路径
    local_paths = ["market/"]
    if search_type == "interview_experiences":
        local_paths.append("interviews/")
    elif search_type == "job_requirements":
        local_paths.append("jds/")

    result = router.search(query, search_type, local_paths)

    return {
        "query": query,
        "search_type": search_type,
        "results": result.get("results", []),
        "has_local_data": result.get("has_local", False),
        "fallback_to_llm": result.get("fallback_to_llm", True),
    }


def _infer_search_type(query: str) -> str:
    """从查询内容推断搜索类型。"""
    query_lower = query.lower()

    # 面试相关
    if any(kw in query_lower for kw in ["面经", "面试", "面试题", "interview"]):
        return "interview_experiences"

    # 薪资相关
    if any(kw in query_lower for kw in ["薪资", "工资", "salary", "待遇", "薪酬"]):
        return "market_trends"

    # JD/岗位要求相关
    if any(kw in query_lower for kw in ["jd", "岗位", "职位", "要求", "job description"]):
        return "job_requirements"

    # 默认：市场趋势
    return "market_trends"


def build_market_search_prompt(query: str, search_results: dict[str, Any]) -> str:
    """构建市场搜索的 LLM prompt。

    如果有本地数据，用本地数据辅助 LLM 分析。
    如果没有，让 LLM 基于自身知识回答。

    Args:
        query: 用户查询
        search_results: search_market_data 的返回值

    Returns:
        prompt 字符串
    """
    prompt_parts = [
        "你是一个就业市场分析师。",
        f"\n## 用户查询\n{query}",
    ]

    # 添加本地搜索结果
    results = search_results.get("results", [])
    local_results = [r for r in results if not r.get("fallback")]

    if local_results:
        prompt_parts.append("\n## 参考数据（本地知识库）")
        for r in local_results[:3]:
            prompt_parts.append(f"\n### 来源：{r['source']}")
            prompt_parts.append(r.get("content", "")[:1000])

    prompt_parts.extend([
        "\n## 请回答",
        "基于以上信息（如有），回答用户的问题。",
        "如果没有本地数据，请基于你的行业知识回答。",
        "",
        "回答格式：",
        "- 先给核心结论",
        "- 再给详细分析",
        "- 如果有数据来源，标注来源",
        "- 如果是估算，明确说明",
    ])

    return "\n".join(prompt_parts)


def format_market_results(query: str, llm_response: str) -> str:
    """格式化市场搜索结果。

    Args:
        query: 用户查询
        llm_response: LLM 的回答

    Returns:
        格式化的 Markdown 文本
    """
    return f"## 🔍 市场搜索：{query}\n\n{llm_response}"
