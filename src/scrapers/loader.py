"""Scraper 加载器——从 config.yaml 读取注册信息，动态加载 Scraper 实现。"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml

from .base import CompanyScraper

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
        # 支持相对路径（相对于 src/scrapers/）和绝对路径
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


def get_scraper(company: str) -> CompanyScraper | None:
    """获取指定公司的 Scraper 实例。"""
    cls = _load_scraper_class(company)
    if cls is None:
        return None
    try:
        return cls()
    except Exception:
        return None


def list_scrapers() -> list[dict[str, Any]]:
    """列出所有已注册的企业 Scraper。

    Returns:
        每个 Scraper 的信息列表：
        [
            {
                "id": "bytedance",
                "name": "字节跳动",
                "description": "...",
                "params": {"keyword": {"description": "...", "required": true}, ...}
            }
        ]
    """
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


def search_company_jobs(company: str, **kwargs: Any) -> dict[str, Any]:
    """搜索指定公司的岗位。

    Args:
        company: 公司 ID（如 bytedance）
        **kwargs: 搜索参数

    Returns:
        {"company": "...", "results": [...], "count": N}
    """
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

    # 补充 company 字段（如果 Scraper 没填）
    scraper_config = _load_config().get("scrapers", {}).get(company, {})
    company_name = scraper_config.get("name", company)
    for r in results:
        r.setdefault("company", company_name)

    return {
        "company": company_name,
        "results": results,
        "count": len(results),
    }


def get_job_detail(url: str, company: str | None = None) -> dict[str, Any]:
    """获取岗位详情。

    如果指定了 company，用对应的 Scraper；
    否则尝试所有 Scraper 直到成功。

    Args:
        url: 岗位详情页 URL
        company: 公司 ID（可选）

    Returns:
        岗位详情 dict。
    """
    if company:
        scraper = get_scraper(company)
        if scraper is None:
            return {"error": f"未找到「{company}」的 Scraper"}
        try:
            return scraper.get_detail(url)
        except Exception as e:
            return {"error": f"获取详情失败: {e}"}

    # 未指定公司，尝试所有 Scraper
    config = _load_config()
    for company_id in config.get("scrapers", {}):
        scraper = get_scraper(company_id)
        if scraper is None:
            continue
        try:
            result = scraper.get_detail(url)
            if result and not result.get("error"):
                return result
        except Exception:
            continue

    return {"error": f"没有 Scraper 能处理此 URL: {url}"}
