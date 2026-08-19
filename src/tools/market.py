"""市场搜索——岗位、薪资、面试信息。"""


def format_search_results(raw_results: str, query: str) -> str:
    """将市场搜索结果格式化为可读摘要。

    Args:
        raw_results: 搜索原始输出
        query: 原始搜索关键词

    Returns:
        Markdown 格式的摘要
    """
    return f"## 市场搜索：{query}\n\n{raw_results}"
