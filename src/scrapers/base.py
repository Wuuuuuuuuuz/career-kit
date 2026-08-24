"""企业 JD 数据源基类——接口规范。

实现者只需：
1. 继承 CompanyScraper
2. 实现 search() 和 get_detail()
3. 在 config.yaml 中注册

框架自动处理：
- 缓存（通过 _cache 方法）
- 知识库写入（loader 层自动调用）
- URL 路由（通过 supports_url 或 config.yaml 中的 url_patterns）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..tools.cache import CacheManager, cache_key as _cache_key_fn


class CompanyScraper(ABC):
    """企业 JD 数据源抽象基类。

    接口规范：
    - search(**kwargs) → list[dict]：搜索岗位，参数由各实现自定义
    - get_detail(url) → dict：获取岗位详情

    返回字段规范（建议，多了不限，少了不强制）：

    search 返回：
        {
            "title": "岗位名称",
            "url": "岗位链接",
            "company": "公司名称",
            "location": "工作地点",
            "department": "部门（可选）",
            "summary": "岗位摘要",
        }

    get_detail 返回：
        {
            "title": "岗位名称",
            "company": "公司名称",
            "location": "工作地点",
            "salary": "薪资范围（可选）",
            "description": "岗位描述全文",
            "requirements": "任职要求全文",
            "benefits": "福利待遇（可选）",
        }
    """

    # === 子类可覆盖的类变量 ===

    # 公司标识，用于日志和知识库目录
    COMPANY_SLUG: str = ""

    # 缓存 TTL（秒），框架层使用
    search_cache_ttl: int = 3600   # 搜索结果 1 小时
    detail_cache_ttl: int = 86400  # 详情 24 小时

    # === 缓存（框架提供，scraper 直接用） ===

    def _make_cache(self, namespace: str) -> CacheManager:
        """创建一个缓存实例，namespace 用于隔离不同类型的缓存。"""
        ttl = self.detail_cache_ttl if namespace == "detail" else self.search_cache_ttl
        cache_dir = Path(__file__).parent / self.COMPANY_SLUG / "cache" / namespace
        return CacheManager(backend="file", ttl=ttl, cache_dir=cache_dir)

    @staticmethod
    def _cache_key(**kwargs: Any) -> str:
        """生成缓存键。"""
        return _cache_key_fn(**kwargs)

    # === URL 路由 ===

    def supports_url(self, url: str) -> bool:
        """判断此 scraper 是否能处理给定的 URL。

        默认实现：从 config.yaml 的 url_patterns 匹配域名。
        子类可覆盖此方法实现更复杂的匹配逻辑。
        """
        # 由 loader 在注册时注入 url_patterns，这里用属性兜底
        patterns = getattr(self, "_url_patterns", [])
        if not patterns:
            return False
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        return any(hostname == p or hostname.endswith(f".{p}") for p in patterns)

    # === 抽象方法（scraper 必须实现） ===

    @abstractmethod
    def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        """搜索岗位。

        Args:
            **kwargs: 搜索参数，由各实现自定义。
                常见参数：keyword, city, department, job_type 等
                具体支持哪些参数见 config.yaml 中的 params 定义。

        Returns:
            岗位列表，每项为一个 dict。
        """

    @abstractmethod
    def get_detail(self, url: str) -> dict[str, Any]:
        """获取岗位详情。

        Args:
            url: 岗位详情页 URL

        Returns:
            岗位详情 dict。
        """
