"""{{COMPANY_NAME}} Scraper — 企业招聘数据源。

实现者：复制此目录，修改 3 处即可。

快速开始：
1. 将此目录复制为 src/scrapers/{company_name}/
2. 修改 COMPANY_SLUG、COMPANY_NAME、BASE_URL
3. 实现 search() 和 get_detail()
4. 在 config.yaml 注册（含 url_patterns）
5. 提交 PR

框架自动处理：
- 缓存（通过 self._make_cache("search" 或 "detail")）
- 知识库写入（loader 层自动调用，无需手动）
- URL 路由（通过 supports_url 或 config.yaml 的 url_patterns）
- 输出校验（title 和 url 会自动补全）
"""

from __future__ import annotations

from typing import Any

import httpx

from ..base import CompanyScraper


class Scraper(CompanyScraper):
    """{{COMPANY_NAME}} Scraper。

    TODO: 修改以下类变量
    """

    COMPANY_SLUG = "{{COMPANY_NAME_EN}}"  # 英文标识，用于缓存目录和日志
    BASE_URL = "https://..."              # 官网地址

    # 按需调整 TTL（秒）
    search_cache_ttl = 3600   # 搜索结果 1 小时
    detail_cache_ttl = 86400  # 详情 24 小时

    def supports_url(self, url: str) -> bool:
        """判断 URL 是否属于此企业。config.yaml 的 url_patterns 会自动注入，
        一般无需覆盖此方法。"""
        return super().supports_url(url)

    def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        """搜索岗位。

        TODO: 实现具体抓取逻辑

        Args:
            keyword: 搜索关键词
            city: 城市名
            job_type: 岗位类别（可选）
            limit: 返回数量上限，默认 20

        Returns:
            岗位列表
        """
        keyword = kwargs.get("keyword", "")
        city = kwargs.get("city", "")
        limit = kwargs.get("limit", 20)

        # 1. 查缓存
        search_cache = self._make_cache("search")
        key = self._cache_key(keyword=keyword, city=city)
        cached = search_cache.get(key)
        if cached is not None:
            return cached[:limit]

        # 2. 抓取数据（TODO: 实现）
        results = self._fetch_jobs(keyword=keyword, city=city, limit=limit)

        # 3. 缓存成功结果（知识库写入由 loader 自动处理）
        if results and "error" not in results[0]:
            search_cache.set(key, results)

        return results[:limit]

    def get_detail(self, url: str) -> dict[str, Any]:
        """获取岗位详情。

        TODO: 实现具体抓取逻辑

        Args:
            url: 岗位详情页 URL

        Returns:
            岗位详情 dict
        """
        # 1. 查缓存
        detail_cache = self._make_cache("detail")
        key = self._cache_key(url=url)
        cached = detail_cache.get(key)
        if cached is not None:
            return cached

        # 2. 抓取详情（TODO: 实现）
        result = self._fetch_detail(url)

        # 3. 缓存成功结果（知识库写入由 loader 自动处理）
        if result and "error" not in result:
            detail_cache.set(key, result)

        return result

    # === 内部方法（TODO: 实现以下方法） ===

    def _fetch_jobs(self, keyword: str, city: str, limit: int) -> list[dict[str, Any]]:
        """具体抓取逻辑。

        TODO: 实现你的抓取方式
        - httpx 直调 API（推荐，简单快速）
        - Playwright XHR 拦截（处理 SPA 页面）
        - httpx + HTML 解析（传统网站）

        Returns:
            岗位列表，每项包含 title, url, company, location, summary
        """
        raise NotImplementedError("请实现 _fetch_jobs 方法")

    def _fetch_detail(self, url: str) -> dict[str, Any]:
        """具体详情逻辑。

        TODO: 实现你的详情抓取方式

        Returns:
            岗位详情 dict，包含 title, company, location, salary, description, requirements
        """
        raise NotImplementedError("请实现 _fetch_detail 方法")
