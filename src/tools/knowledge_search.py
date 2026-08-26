"""知识库检索——搜索本地积累的求职资料。

只检索 data/knowledge/ 目录（含 scraper 自动写入的 JD/面经 + 用户手动放入的资料）。
不做任何网络请求，不调用 LLM——没有数据时诚实告知，
并引导使用 fetch_company_jobs 获取实时数据。
"""

from __future__ import annotations

from typing import Any

from ..paths import KNOWLEDGE_DIR

SUPPORTED_EXTENSIONS = {".md", ".txt", ".json"}

# 通用搜索词——提取关键词时跳过
_STOP_WORDS = frozenset({
    "jd", "要求", "必备", "技能", "简历", "模板", "筛选", "标准",
    "关键词", "面试", "经验", "面经", "薪资", "趋势", "市场",
    "岗位", "职位", "描述", "分析", "参考", "案例", "同背景",
    "前辈", "候选", "画像", "准备", "通过",
})

# 公司别名 → 知识库目录名
_COMPANY_ALIASES = {
    "字节": "bytedance",
    "bytedance": "bytedance",
    "字节跳动": "bytedance",
    "boss": "boss",
    "boss直聘": "boss",
    "牛客": "nowcoder",
    "nowcoder": "nowcoder",
}


def _split_chinese_text(text: str) -> list[str]:
    """简易中文分词：按标点/空白切分，再对长中文串做 2-gram。"""
    import re
    tokens = re.split(r"[\s,，。.、;；:：!！?？()（）\[\]【】]+", text)
    result = []
    for token in tokens:
        token = token.strip().lower()
        if not token:
            continue
        if len(token) <= 3:
            result.append(token)
        else:
            # 长串切 2-gram 提高召回
            for i in range(len(token) - 1):
                gram = token[i:i + 2]
                if gram not in _STOP_WORDS:
                    result.append(gram)
    return list(dict.fromkeys(result))


def search_knowledge(query: str, limit: int = 5) -> dict[str, Any]:
    """检索本地知识库。

    Args:
        query: 搜索关键词（如 "AI Agent 面经"、"字节跳动 JD"）
        limit: 返回条数上限

    Returns:
        {"results": [...], "count": int, "knowledge_dir": str}
    """
    if not KNOWLEDGE_DIR.exists():
        return {"results": [], "count": 0, "knowledge_dir": str(KNOWLEDGE_DIR)}

    query_lower = query.lower()
    all_tokens = list(dict.fromkeys(
        [t for t in _split_chinese_text(query) if t not in _STOP_WORDS]
        + [w for w in query_lower.split() if len(w) >= 2]
    )) or ([query_lower] if len(query_lower) >= 2 else [])

    results = []
    for file_path in KNOWLEDGE_DIR.rglob("*"):
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            continue

        rel_path = file_path.relative_to(KNOWLEDGE_DIR).as_posix()
        content_lower = content.lower()
        filename_lower = file_path.name.lower()

        score = 0.0
        for token in all_tokens:
            count = content_lower.count(token)
            score += min(count * 0.1, 1.0)
            if token in filename_lower:
                score += 2.0
        if len(query_lower) >= 2 and query_lower in content_lower:
            score += 1.0

        if score > 0:
            results.append({
                "source": rel_path,
                "content": content[:2000],
                "relevance": round(score, 2),
            })

    results.sort(key=lambda x: x["relevance"], reverse=True)
    return {
        "results": results[:limit],
        "count": len(results),  # 真实命中数，而非截断后的条数（显示「找到 N 条」时不能骗人）
        "knowledge_dir": str(KNOWLEDGE_DIR),
    }
