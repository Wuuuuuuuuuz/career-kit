"""Scraper 加载器——从 config.yaml 读取注册信息，动态加载 Scraper 实现。

框架层职责：
- 动态加载和缓存 Scraper 类
- 搜索/详情成功后自动写入知识库
- URL 路由：按 supports_url 匹配最合适的 Scraper
- 输出校验：确保 title 和 url 字段存在
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

import yaml

from .base import CompanyScraper
from .knowledge_writer import write_to_knowledge

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.yaml"

# 缓存已加载的 Scraper 类
_scraper_classes: dict[str, type[CompanyScraper]] = {}
_config: dict[str, Any] | None = None


def _load_config() -> dict[str, Any]:
    """加载 config.yaml。"""
    global _config
    if _config is None:
        if not CONFIG_PATH.exists():
            _config = {"scrapers": {}}
        else:
            raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raw = {}
            raw.setdefault("scrapers", {})
            if raw["scrapers"] is None:
                raw["scrapers"] = {}
            _config = raw
    return _config


def _load_scraper_class(company: str) -> type[CompanyScraper] | None:
    """动态加载指定公司的 Scraper 类。"""
    if company in _scraper_classes:
        return _scraper_classes[company]

    config = _load_config()
    scraper_config = config.get("scrapers", {}).get(company)
    if not scraper_config:
        return None

    module_path = scraper_config.get("module", "")
    class_name = scraper_config.get("class", "Scraper")

    if not module_path:
        return None

    try:
        if not module_path.startswith("src."):
            full_path = f"src.scrapers.{module_path}" if module_path else ""
        else:
            full_path = module_path
        module = importlib.import_module(full_path)
        cls = getattr(module, class_name)
        if not issubclass(cls, CompanyScraper):
            return None
        _scraper_classes[company] = cls
        return cls
    except (ImportError, AttributeError, TypeError):
        return None


def _instantiate_scraper(company: str) -> CompanyScraper | None:
    """实例化 Scraper 并注入 config 信息（url_patterns 等）。"""
    cls = _load_scraper_class(company)
    if cls is None:
        return None
    try:
        scraper = cls()
    except Exception:
        return None

    # 注入 config.yaml 中的 url_patterns
    config = _load_config()
    scraper_config = config.get("scrapers", {}).get(company, {})
    url_patterns = scraper_config.get("url_patterns", [])
    scraper._url_patterns = url_patterns

    # 注入 COMPANY_SLUG（如果子类没设）
    if not scraper.COMPANY_SLUG:
        scraper.COMPANY_SLUG = company

    return scraper


def get_scraper(company: str) -> CompanyScraper | None:
    """获取指定公司的 Scraper 实例。"""
    return _instantiate_scraper(company)


def list_scrapers() -> list[dict[str, Any]]:
    """列出所有已注册的企业 Scraper。"""
    config = _load_config()
    result = []
    for company_id, info in config.get("scrapers", {}).items():
        result.append({
            "id": company_id,
            "name": info.get("name", company_id),
            "description": info.get("description", ""),
            "params": info.get("params", {}),
        })
    return result


def get_scraper_for_url(url: str) -> CompanyScraper | None:
    """根据 URL 匹配最合适的 Scraper。

    优先用 supports_url() 匹配，避免盲遍历。
    """
    config = _load_config()
    for company_id in config.get("scrapers", {}):
        scraper = get_scraper(company_id)
        if scraper is None:
            continue
        if scraper.supports_url(url):
            return scraper
    return None


def _validate_results(results: list[dict[str, Any]], company_name: str) -> list[dict[str, Any]]:
    """校验搜索结果，补全缺失的必要字段。"""
    validated = []
    for r in results:
        if not isinstance(r, dict):
            continue
        if not r.get("title"):
            r["title"] = "未知岗位"
            logger.warning(f"{company_name}: 搜索结果缺少 title 字段")
        if not r.get("url"):
            r["url"] = ""
            logger.warning(f"{company_name}: 搜索结果缺少 url 字段")
        validated.append(r)
    return validated


def _auto_write_knowledge(company: str, data: Any, data_type: str = "jds") -> None:
    """自动写入知识库。scraper 无需手动调用。"""
    try:
        config = _load_config()
        module_path = config.get("scrapers", {}).get(company, {}).get("module", "")
        if not module_path:
            return
        full_module = f"src.scrapers.{module_path}"
        write_to_knowledge(full_module, data, data_type=data_type)
    except Exception as e:
        logger.warning(f"知识库写入失败 ({company}): {e}")


def search_company_jobs(company: str, **kwargs: Any) -> dict[str, Any]:
    """搜索指定公司的岗位。自动处理缓存、校验、知识库写入。"""
    scraper = get_scraper(company)
    if scraper is None:
        config = _load_config()
        available = list(config.get("scrapers", {}).keys())
        return {
            "error": f"未找到「{company}」的 Scraper",
            "available": available,
        }

    try:
        results = scraper.search(**kwargs)
    except Exception as e:
        return {"error": f"搜索失败: {e}", "results": []}

    # 从 config 补充 company 字段
    scraper_config = _load_config().get("scrapers", {}).get(company, {})
    company_name = scraper_config.get("name", company)
    for r in results:
        r.setdefault("company", company_name)

    # 校验输出
    results = _validate_results(results, company_name)

    # 自动写入知识库
    if results and not any(r.get("error") for r in results):
        _auto_write_knowledge(company, results)

    return {
        "company": company_name,
        "results": results,
        "count": len(results),
    }


def get_job_detail(url: str, company: str | None = None) -> dict[str, Any]:
    """获取岗位详情。自动处理缓存、URL 路由、知识库写入。"""
    if company:
        scraper = get_scraper(company)
        if scraper is None:
            return {"error": f"未找到「{company}」的 Scraper"}
        try:
            result = scraper.get_detail(url)
        except Exception as e:
            return {"error": f"获取详情失败: {e}"}
    else:
        # URL 路由：先用 supports_url 匹配
        scraper = get_scraper_for_url(url)
        if scraper:
            try:
                result = scraper.get_detail(url)
            except Exception as e:
                return {"error": f"获取详情失败: {e}"}
        else:
            # 兜底：遍历所有 Scraper
            config = _load_config()
            result = None
            for company_id in config.get("scrapers", {}):
                s = get_scraper(company_id)
                if s is None:
                    continue
                try:
                    r = s.get_detail(url)
                    if r and not r.get("error"):
                        result = r
                        break
                except Exception:
                    continue
            if result is None:
                return {"error": f"没有 Scraper 能处理此 URL: {url}"}

    # 自动写入知识库
    if result and not result.get("error"):
        # 从 URL 推断 company
        if not company:
            # 尝试从 result 中获取 company
            slug = result.get("company_slug", "")
            if slug:
                company = slug
            else:
                # 从 supports_url 匹配的 scraper 获取
                matched = get_scraper_for_url(url)
                if matched:
                    company = matched.COMPANY_SLUG
        if company:
            _auto_write_knowledge(company, result)

    return result
