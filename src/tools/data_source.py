"""数据源接口——检索层抽象。

数据源分层：
1. 本地知识库（dev/knowledge/）— 用户积累的面经/JD/参考简历
2. LLM 知识 — 基于模型训练数据的行业知识（兜底）
3. Web Search API — 实时搜索（TODO: 后续接入）

每个数据源实现 DataSource 接口，DataRouter 按优先级路由。
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


# 本地知识库根目录
KNOWLEDGE_DIR = Path(__file__).parent.parent.parent / "dev" / "knowledge"

# 公司名映射：中文名/常用别名 → 目录名
# 目录名通常用英文小写拼音或英文名
COMPANY_ALIASES: dict[str, str] = {
    # 大厂
    "字节跳动": "bytedance", "字节": "bytedance", "抖音": "bytedance", "头条": "bytedance",
    "腾讯": "tencent", "微信": "tencent",
    "阿里巴巴": "alibaba", "阿里": "alibaba", "淘宝": "alibaba", "蚂蚁": "alibaba",
    "百度": "baidu",
    "美团": "meituan", "大众点评": "meituan",
    "京东": "jd", "jd.com": "jd",
    "网易": "netease",
    "小米": "xiaomi",
    "华为": "huawei",
    "拼多多": "pinduoduo", "pdd": "pinduoduo",
    "快手": "kuaishou",
    "小红书": "xiaohongshu", "red": "xiaohongshu",
    "携程": "ctrip", "trip.com": "ctrip",
    "滴滴": "didi",
    "bilibili": "bilibili", "b站": "bilibili", "哔哩哔哩": "bilibili",
    "新浪": "sina", "微博": "sina",
    "搜狐": "sohu",
    "微软": "microsoft", "ms": "microsoft",
    "谷歌": "google",
    "苹果": "apple",
    "亚马逊": "amazon", "aws": "amazon",
    "meta": "meta", "脸书": "meta", "facebook": "meta",
    "openai": "openai",
    "英伟达": "nvidia",
    # 独角兽
    "商汤": "sensetime",
    "旷视": "megvii",
    "智谱": "zhipu", "智谱ai": "zhipu",
    "月之暗面": "moonshot", "kimi": "moonshot",
    "minimax": "minimax",
    "零一万物": "01.ai",
    "百川": "baichuan",
    "deepseek": "deepseek",
}


def _split_chinese_text(text: str) -> list[str]:
    """简单中文分词：按空格、标点、中英文边界拆分。

    不依赖外部分词库，适用于关键词匹配场景。
    """
    # 统一小写
    text = text.lower()
    # 按空格、标点、特殊字符分割
    tokens = re.split(r'[\s,，.。!！?？;；:：、/\-_()\[\]{}（）【】《》]+', text)
    # 过滤空串和单字符（中文单字噪声太多）
    return [t for t in tokens if len(t) >= 2]


def _extract_company_from_path(rel_path: str) -> str | None:
    """从相对路径提取公司名。

    约定：jds/ 和 interviews/ 下的二级目录为公司名。
    如 jds/bytedance/xxx.json → bytedance
    如 interviews/tencent/backend.md → tencent
    market/ 和 resumes/ 不按公司分目录，返回 None。
    """
    COMPANY_DIRS = ("jds", "interviews")
    parts = Path(rel_path).parts
    if len(parts) >= 3 and parts[0] in COMPANY_DIRS:
        # jds/bytedance/xxx.json → parts = ('jds', 'bytedance', 'xxx.json')
        return parts[1]
    return None


def _resolve_company_alias(query: str) -> str | None:
    """尝试将查询中的公司名别名解析为目录名。"""
    query_lower = query.lower().strip()
    # 精确匹配
    if query_lower in COMPANY_ALIASES:
        return COMPANY_ALIASES[query_lower]
    # 查询中包含别名
    for alias, dirname in COMPANY_ALIASES.items():
        if alias in query_lower:
            return dirname
    return None


class DataSource(ABC):
    """数据源抽象接口。"""

    @abstractmethod
    def search(self, query: str, search_type: str, paths: list[str] | None = None) -> list[dict[str, Any]]:
        """搜索数据。

        Args:
            query: 搜索查询
            search_type: 搜索类型（similar_profiles / job_requirements / interview_experiences / market_trends）
            paths: 本地搜索路径（相对于 knowledge/ 目录），用于过滤和定向搜索

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
            search_dirs = [d for d in KNOWLEDGE_DIR.iterdir() if d.is_dir()]

        # 尝试从查询中解析公司别名，用于额外加分
        resolved_company = _resolve_company_alias(query)

        for search_dir in search_dirs:
            for file_path in search_dir.rglob("*"):
                if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                except Exception:
                    continue

                rel_path = str(file_path.relative_to(KNOWLEDGE_DIR))
                company = _extract_company_from_path(rel_path)

                relevance = self._calculate_relevance(query, content, file_path.name, rel_path)

                # 如果查询包含公司别名，且文件所在目录匹配该公司，额外加分
                if resolved_company and company and company == resolved_company:
                    relevance += 1.5

                if relevance > 0:
                    results.append({
                        "source": f"本地文件: {rel_path}",
                        "content": content[:2000],
                        "relevance": relevance,
                        "path": str(file_path),
                        "company": company,
                    })

        # 按相关度排序
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:5]

    def _calculate_relevance(self, query: str, content: str, filename: str, rel_path: str = "") -> float:
        """计算相关度（关键词匹配 + 文件名加权 + 中文分词）。

        匹配策略：
        1. 对查询和内容都做中文分词
        2. 文件名/路径匹配权重高于内容匹配（文件名通常包含关键信息）
        3. 精确短语匹配额外加分

        TODO: 后续替换为 embedding 语义搜索。
        """
        query_lower = query.lower()
        content_lower = content.lower()
        filename_lower = filename.lower()
        path_lower = rel_path.lower()

        score = 0.0

        # 中文分词：将查询拆成有意义的 token
        query_tokens = _split_chinese_text(query)
        # 也保留空格分割的原始词（兼容英文查询）
        query_words = [w for w in query_lower.split() if len(w) >= 2]
        # 合并去重
        all_tokens = list(set(query_tokens + query_words))

        if not all_tokens:
            # fallback: 整个查询作为单个 token
            all_tokens = [query_lower] if len(query_lower) >= 2 else []

        for token in all_tokens:
            # 内容匹配：每出现一次加分，上限 1.0
            count = content_lower.count(token)
            score += min(count * 0.1, 1.0)

            # 文件名匹配：权重 2.0（文件名通常包含关键信息）
            if token in filename_lower:
                score += 2.0

            # 路径匹配：权重 1.5（路径中的公司名等目录信息）
            if token in path_lower and token not in filename_lower:
                score += 1.5

        # 精确短语匹配：查询整体出现在内容中，额外加分
        if len(query_lower) >= 2 and query_lower in content_lower:
            score += 1.0

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


# 通用搜索词——提取关键词时跳过
_STOP_WORDS = frozenset({
    "jd", "要求", "必备", "技能", "简历", "模板", "筛选", "标准",
    "关键词", "面试", "经验", "面经", "薪资", "趋势", "市场",
    "岗位", "职位", "描述", "分析", "参考", "案例", "同背景",
    "前辈", "候选", "画像", "准备", "通过",
})


def _extract_search_keywords(query: str) -> str:
    """从 SOP 查询模板生成的文本中提取搜索关键词。

    SOP 的 query_template 会产生类似 "前端开发 大厂 JD 要求 必备技能" 的文本，
    需要过滤掉通用搜索词，保留有意义的关键词如 "前端开发"。
    """
    tokens = _split_chinese_text(query)
    keywords = [t for t in tokens if t not in _STOP_WORDS]
    return " ".join(keywords) if keywords else query


class ScraperSource(DataSource):
    """企业 Scraper 数据源——本地知识库为空时，自动从注册的 Scraper 获取真实数据。

    在 DataRouter 优先级链中位于 LocalKnowledgeSource 之后、LLMKnowledgeSource 之前。
    Scraper 获取的数据会自动写入知识库（通过 loader 自动调用 knowledge_writer），后续检索直接命中本地缓存。

    搜索策略：
    - 如果 query 包含明确的公司名，只搜索该公司的 Scraper
    - 否则遍历所有 Scraper
    """

    def search(self, query: str, search_type: str, paths: list[str] | None = None) -> list[dict[str, Any]]:
        # 仅对 JD 相关搜索触发 Scraper（interview 和 market 暂无 scraper 支持）
        if search_type not in ("job_requirements", "similar_profiles"):
            return []

        try:
            from ..scrapers.loader import search_company_jobs, list_scrapers
        except ImportError as e:
            return [self._error_result(
                "scraper_import_error",
                f"企业 Scraper 加载失败（缺少依赖）：{e}。请运行 pip install playwright && playwright install chromium",
            )]

        scrapers = list_scrapers()
        if not scrapers:
            return [self._error_result(
                "no_scrapers",
                "未注册任何企业 Scraper。请在 src/scrapers/config.yaml 中添加配置。",
            )]

        keyword = _extract_search_keywords(query)

        # 智能过滤：如果 query 包含公司名，只搜该公司的 scraper
        resolved_company = _resolve_company_alias(query)
        target_scrapers = scrapers
        if resolved_company:
            matched = [s for s in scrapers if s["id"] == resolved_company]
            if matched:
                target_scrapers = matched

        all_results = []
        errors = []
        for scraper_info in target_scrapers:
            company_id = scraper_info["id"]
            try:
                result = search_company_jobs(company_id, keyword=keyword)
            except Exception as e:
                errors.append(f"{company_id}: {e}")
                continue

            if result.get("error"):
                errors.append(f"{company_id}: {result['error']}")
                continue

            if not result.get("results"):
                continue

            for job in result["results"][:5]:
                parts = [job.get("title", "")]
                if job.get("location"):
                    parts.append(job["location"])
                if job.get("summary"):
                    parts.append(job["summary"])
                elif job.get("description"):
                    parts.append(job["description"][:300])

                all_results.append({
                    "source": f"企业招聘: {result.get('company', company_id)}",
                    "content": "\n".join(parts),
                    "relevance": 1.0,
                    "company": company_id,
                    "url": job.get("url", ""),
                })

        # 有结果就返回结果（错误作为附带信息）
        if all_results:
            return all_results

        # 无结果：返回错误信息，不静默吞掉
        if errors:
            return [self._error_result(
                "scraper_failed",
                f"企业 Scraper 搜索失败：{'; '.join(errors)}。可能需要安装 Playwright 环境：pip install playwright && playwright install chromium",
            )]

        # Scraper 正常运行但无匹配结果
        return []

    @staticmethod
    def _error_result(code: str, message: str) -> dict[str, Any]:
        return {
            "source": "ScraperSource",
            "content": f"[{code}] {message}",
            "relevance": 0,
            "scraper_error": True,
            "error_code": code,
        }


# DEPRECATED: Web Search API 不再计划接入
# 设计决策：数据获取应通过企业爬虫（Scraper）提供，而非通用搜索 API
# 原因：
# 1. LLM 自身已有搜索能力，无需额外搜索 API
# 2. 企业爬虫能获取结构化、高质量的岗位数据
# 3. 避免依赖外部付费 API，保持项目开源独立性
# 数据源架构：本地知识库 → 企业 Scraper → LLM 知识（兜底）


class DataRouter:
    """数据路由器——按优先级尝试不同数据源。

    优先级：
    1. 本地知识库（用户积累的面经/JD/参考简历）
    2. 企业 Scraper（实时获取真实 JD 数据）
    3. LLM 知识（兜底）

    返回值中 scraper_errors 记录 Scraper 失败原因，上层应提示用户而非静默忽略。
    """

    def __init__(self):
        self.sources: list[DataSource] = [
            LocalKnowledgeSource(),
            ScraperSource(),
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
                "results": [...],           # 搜索结果
                "has_local": bool,          # 是否有本地数据
                "fallback_to_llm": bool,    # 是否需要 LLM 兜底
                "scraper_errors": [...],    # Scraper 错误信息（如有）
            }
        """
        all_results = []
        has_local = False
        scraper_errors = []

        for source in self.sources:
            results = source.search(query, search_type, paths)
            if not results:
                continue

            # 分离 Scraper 错误和正常结果
            if isinstance(source, ScraperSource):
                errors = [r for r in results if r.get("scraper_error")]
                real_results = [r for r in results if not r.get("scraper_error")]
                if errors:
                    scraper_errors.extend(r["content"] for r in errors)
                if real_results:
                    has_local = True
                    all_results.extend(real_results)
            elif any(r.get("fallback") for r in results):
                if not has_local:
                    all_results.extend(results)
            else:
                has_local = True
                all_results.extend(results)

        return {
            "results": all_results,
            "has_local": has_local,
            "fallback_to_llm": not has_local,
            "scraper_errors": scraper_errors,
        }
