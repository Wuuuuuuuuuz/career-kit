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
    """列出所有已注册的企业 Scraper。

    参数定义以 scraper 类的 PARAMS 类属性为唯一事实源；
    未声明 PARAMS 的旧式 scraper 回退到 config.yaml 的 params 段。
    """
    config = _load_config()
    result = []
    for company_id, info in config.get("scrapers", {}).items():
        params = info.get("params") or {}
        source = "config"

        # 类属性 PARAMS 优先（单一事实源在代码里，随实现同步演化）
        cls = _load_scraper_class(company_id)
        if cls is not None and getattr(cls, "PARAMS", None):
            params = cls.PARAMS
            source = "class"

        result.append({
            "id": company_id,
            "name": info.get("name", company_id),
            "description": info.get("description", ""),
            "params": params,
            "params_source": source,
        })
    return result


def read_scraper_guide(company: str) -> str | None:
    """读取指定企业源的 guide.md 使用教程。

    教程随 scraper 包分发（唯一事实源），未提供时返回 None。
    """
    guide_path = Path(__file__).parent / company / "guide.md"
    if not guide_path.exists():
        return None
    try:
        return guide_path.read_text(encoding="utf-8")
    except OSError:
        return None


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
    """校验搜索结果，补全缺失的必要字段。

    错误条目（含 "error" 键）原样保留，不做字段装饰——
    否则内部失败会被伪装成「未知岗位」假数据。
    """
    validated = []
    for r in results:
        if not isinstance(r, dict):
            continue
        if r.get("error"):
            validated.append(r)
            continue
        if not r.get("title"):
            r["title"] = "未知岗位"
            logger.warning(f"{company_name}: 搜索结果缺少 title 字段")
        if not r.get("url"):
            r["url"] = ""
            logger.warning(f"{company_name}: 搜索结果缺少 url 字段")
        validated.append(r)
    return validated


def _auto_write_knowledge(company: str, data: Any, data_type: str | None = None) -> None:
    """自动写入知识库。scraper 无需手动调用。

    data_type 优先级：参数 > config.yaml > scraper 类属性 > 默认 "jds"
    """
    try:
        config = _load_config()
        scraper_config = config.get("scrapers", {}).get(company, {})
        module_path = scraper_config.get("module", "")
        if not module_path:
            return

        # 确定 data_type
        if data_type is None:
            data_type = scraper_config.get("data_type", "")

        if not data_type:
            # 尝试从 scraper 类属性获取
            scraper = get_scraper(company)
            if scraper and hasattr(scraper, "DATA_TYPE"):
                data_type = scraper.DATA_TYPE

        if not data_type:
            data_type = "jds"

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

    # 分离错误条目和有效结果
    # scraper 内部失败以 [{"error": "..."}] 形式返回，
    # 不能当作岗位数据透传（否则显示为「未知岗位」假结果）
    error_items = [r for r in results if isinstance(r, dict) and r.get("error")]
    valid_items = [r for r in results if isinstance(r, dict) and not r.get("error")]

    # 从 config 补充 company 字段
    scraper_config = _load_config().get("scrapers", {}).get(company, {})
    company_name = scraper_config.get("name", company)
    for r in valid_items:
        r.setdefault("company", company_name)

    # 校验输出（仅对有效结果）
    valid_items = _validate_results(valid_items, company_name)

    # 全部失败：把第一个底层错误上抛，让上层看到真实原因
    if not valid_items and error_items:
        return {"error": error_items[0]["error"], "results": []}

    # 自动写入知识库
    if valid_items:
        _auto_write_knowledge(company, valid_items)

    resp: dict[str, Any] = {
        "company": company_name,
        "results": valid_items,
        "count": len(valid_items),
    }
    if error_items:
        # 部分失败：有效结果照常返回，错误作为警告附带上报
        resp["warnings"] = [r["error"] for r in error_items]
    return resp


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
