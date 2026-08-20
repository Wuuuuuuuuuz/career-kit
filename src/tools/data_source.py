"""数据源接口——检索层抽象。

数据源分层：
1. 本地知识库（dev/knowledge/）— 用户积累的面经/JD/参考简历
2. LLM 知识 — 基于模型训练数据的行业知识（兜底）
3. Web Search API — 实时搜索（TODO: 后续接入）

每个数据源实现 DataSource 接口，DataRouter 按优先级路由。
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


# 本地知识库根目录
KNOWLEDGE_DIR = Path(__file__).parent.parent.parent / "dev" / "knowledge"


class DataSource(ABC):
    """数据源抽象接口。"""

    @abstractmethod
    def search(self, query: str, search_type: str, paths: list[str] | None = None) -> list[dict[str, Any]]:
        """搜索数据。

        Args:
            query: 搜索查询
            search_type: 搜索类型（similar_profiles / job_requirements / interview_experiences / market_trends）
            paths: 本地搜索路径（相对于 knowledge/ 目录）

        Returns:
            搜索结果列表，每项包含 {"source": "来源", "content": "内容", "relevance": "相关度"}
        """


class LocalKnowledgeSource(DataSource):
    """本地知识库数据源。

    从 dev/knowledge/ 目录下读取用户积累的文件。
    支持 .md / .txt / .json 格式。
    """

    SUPPORTED_EXTENSIONS = {".md", ".txt", ".json"}

    def search(self, query: str, search_type: str, paths: list[str] | None = None) -> list[dict[str, Any]]:
        if not KNOWLEDGE_DIR.exists():
            return []

        results = []
        search_dirs = []

        # 确定搜索目录
        if paths:
            for p in paths:
                full_path = KNOWLEDGE_DIR / p
                if full_path.exists():
                    search_dirs.append(full_path)
        else:
            # 搜所有子目录
            if KNOWLEDGE_DIR.exists():
                search_dirs = [d for d in KNOWLEDGE_DIR.iterdir() if d.is_dir()]

        for search_dir in search_dirs:
            for file_path in search_dir.rglob("*"):
                if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                except Exception:
                    continue

                # 简单关键词匹配（TODO: 后续用 embedding 语义搜索）
                relevance = self._calculate_relevance(query, content, file_path.name)
                if relevance > 0:
                    results.append({
                        "source": f"本地文件: {file_path.relative_to(KNOWLEDGE_DIR)}",
                        "content": content[:2000],  # 截断，避免过长
                        "relevance": relevance,
                        "path": str(file_path),
                    })

        # 按相关度排序
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:5]  # 最多返回 5 条

    def _calculate_relevance(self, query: str, content: str, filename: str) -> float:
        """计算相关度（简单关键词匹配）。

        TODO: 后续替换为 embedding 语义搜索。
        """
        query_lower = query.lower()
        content_lower = content.lower()
        filename_lower = filename.lower()

        score = 0.0

        # 查询词在内容中出现的次数
        for word in query_lower.split():
            if len(word) < 2:
                continue
            count = content_lower.count(word)
            score += min(count * 0.1, 1.0)  # 每个词最多贡献 1 分

            # 文件名匹配加分
            if word in filename_lower:
                score += 0.5

        return score


class LLMKnowledgeSource(DataSource):
    """LLM 知识数据源（兜底）。

    不实际搜索，而是返回提示信息，让 LLM 基于自身知识回答。
    """

    def search(self, query: str, search_type: str, paths: list[str] | None = None) -> list[dict[str, Any]]:
        # 返回空列表，但标记需要 LLM 兜底
        return [{
            "source": "LLM 知识（基于训练数据）",
            "content": "",  # 内容由 LLM 在分析时自行补充
            "relevance": 0.5,
            "fallback": True,
        }]


# TODO: 后续接入 Web Search API
# class WebSearchSource(DataSource):
#     """Web 搜索数据源。"""
#
#     def __init__(self, api_key: str | None = None):
#         self.api_key = api_key or os.environ.get("SEARCH_API_KEY")
#
#     def search(self, query: str, search_type: str, paths: list[str] | None = None) -> list[dict[str, Any]]:
#         # TODO: 接入 Tavily / SerpAPI / Bing Search
#         pass


class DataRouter:
    """数据路由器——按优先级尝试不同数据源。

    优先级：
    1. 本地知识库（用户积累的面经/JD/参考简历）
    2. LLM 知识（兜底）
    3. Web Search API（TODO: 后续接入）
    """

    def __init__(self):
        self.sources: list[DataSource] = [
            LocalKnowledgeSource(),
            LLMKnowledgeSource(),
            # TODO: WebSearchSource(),  # 后续接入
        ]

    def search(
        self,
        query: str,
        search_type: str,
        paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """路由搜索请求。

        Args:
            query: 搜索查询
            search_type: 搜索类型
            paths: 本地搜索路径

        Returns:
            {
                "results": [...],       # 搜索结果
                "has_local": bool,      # 是否有本地数据
                "fallback_to_llm": bool # 是否需要 LLM 兜底
            }
        """
        all_results = []
        has_local = False

        for source in self.sources:
            results = source.search(query, search_type, paths)
            if results:
                # 检查是否是 LLM 兜底标记
                if any(r.get("fallback") for r in results):
                    if not has_local:
                        # 没有本地数据，需要用 LLM 兜底
                        all_results.extend(results)
                else:
                    has_local = True
                    all_results.extend(results)

        return {
            "results": all_results,
            "has_local": has_local,
            "fallback_to_llm": not has_local,
        }
