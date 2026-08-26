"""BOSS 直聘 Scraper——requests + iv8 计算 stoken。

核心思路：
1. python -m src.scrapers.boss.login 扫码登录 → 保存 cookies（一次性）
2. requests + cookies → 搜索/详情
3. iv8 计算 __zp_stoken__（处理 code=37）
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from ..base import CompanyScraper
from .auth import load_cookies, has_valid_cookies
from .stoken import get_stoken, handle_code37

# 常量
BASE_URL = "https://www.zhipin.com"
SEARCH_URL = f"{BASE_URL}/wapi/zpgeek/search/joblist.json"
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"

# 城市码表
_CITY_CODES_PATH = Path(__file__).parent / "city_codes.json"
_CITY_MAP: dict[str, str] | None = None


def _load_city_map() -> dict[str, str]:
    """加载城市码表。"""
    global _CITY_MAP
    if _CITY_MAP is None:
        try:
            _CITY_MAP = json.loads(_CITY_CODES_PATH.read_text(encoding="utf-8"))
        except Exception:
            _CITY_MAP = {"全国": "100010000"}
    return _CITY_MAP


def _resolve_city(city: str) -> str:
    """解析城市名/代码。"""
    city_map = _load_city_map()
    code = city_map.get(city, city)
    if not code.isdigit():
        code = city_map.get("全国", "100010000")
    return code


def _build_headers(cookies: dict[str, str], stoken: str | None = None) -> dict:
    """构建请求头。"""
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
    if stoken:
        cookie_str += f"; __zp_stoken__={stoken}"

    return {
        "User-Agent": DEFAULT_UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.zhipin.com/web/geek/job",
        "Origin": "https://www.zhipin.com",
        "Cookie": cookie_str,
    }


def _map_job(raw: dict) -> dict:
    """映射 API 返回的职位数据。"""
    encrypt_job_id = str(raw.get("encryptJobId") or "")
    location_parts = [
        raw.get("cityName") or "",
        raw.get("areaDistrict") or "",
        raw.get("businessDistrict") or "",
    ]
    location = "·".join(p for p in location_parts if p)

    return {
        "title": raw.get("jobName") or "",
        "salary": raw.get("salaryDesc") or "",
        "location": location,
        "company": raw.get("brandName") or "",
        "experience": raw.get("jobExperience") or "",
        "degree": raw.get("jobDegree") or "",
        "url": f"{BASE_URL}/job_detail/{encrypt_job_id}.html" if encrypt_job_id else "",
        "job_id": encrypt_job_id,
        "source": "boss",
    }


def _parse_detail_html(html: str) -> dict:
    """从 HTML 解析岗位详情。"""
    # 提取 JD（核心）
    description = ""
    for pattern in [
        r'<div[^>]*class="job-sec-text"[^>]*>(.*?)</div>',
        r'<div[^>]*class="job-detail-section"[^>]*>.*?<div[^>]*class="job-sec-text"[^>]*>(.*?)</div>',
    ]:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            description = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            description = re.sub(r'\s+', ' ', description)
            break

    # 如果正则失败，尝试 JSON-LD
    if not description:
        json_ld_match = re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
        if json_ld_match:
            try:
                json_ld = json.loads(json_ld_match.group(1))
                description = json_ld.get("description", "")
            except Exception:
                pass

    # 提取其他字段
    title = ""
    for pattern in [r'<h1[^>]*class="job-name"[^>]*>(.*?)</h1>', r'<title>(.*?)招聘']:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            break

    salary = ""
    match = re.search(r'<span[^>]*class="salary"[^>]*>(.*?)</span>', html, re.DOTALL)
    if match:
        salary = re.sub(r'<[^>]+>', '', match.group(1)).strip()

    location = ""
    match = re.search(r'<span[^>]*class="job-area"[^>]*>(.*?)</span>', html, re.DOTALL)
    if match:
        location = re.sub(r'<[^>]+>', '', match.group(1)).strip()

    company = ""
    match = re.search(r'<a[^>]*class="company-name"[^>]*>(.*?)</a>', html, re.DOTALL)
    if match:
        company = re.sub(r'<[^>]+>', '', match.group(1)).strip()

    return {
        "title": title,
        "company": company,
        "location": location,
        "salary": salary,
        "description": description,
        "source": "boss",
    }


class Scraper(CompanyScraper):
    """BOSS 直聘 Scraper。"""

    COMPANY_SLUG = "boss"
    search_cache_ttl = 3600
    detail_cache_ttl = 86400

    # 搜索参数定义（唯一事实源，list_data_sources 渲染给 LLM）
    PARAMS: dict[str, dict[str, Any]] = {
        "keyword": {"required": True, "description": "搜索关键词（如 \"Python\"、\"前端\"、\"AI\"）"},
        "city": {"required": False, "description": "城市名（如 \"北京\"、\"上海\"、\"全国\"）或城市代码"},
        "experience": {"required": False, "description": "经验要求（如 \"1-3年\"、\"3-5年\"、\"不限\"）"},
        "degree": {"required": False, "description": "学历要求（如 \"本科\"、\"硕士\"、\"不限\"）"},
        "salary": {"required": False, "description": "薪资范围（如 \"15-25K\"、\"30-50K\"）"},
        "limit": {"required": False, "description": "返回数量上限，默认 20"},
    }

    def supports_url(self, url: str) -> bool:
        return "zhipin.com" in url

    def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        """搜索岗位。"""
        keyword = kwargs.get("keyword", "")
        city = kwargs.get("city", "全国")
        limit = kwargs.get("limit", 20)

        if not keyword:
            return [{"error": "搜索关键词不能为空"}]

        # 查缓存
        search_cache = self._make_cache("search")
        city_code = _resolve_city(city)
        key = self._cache_key(keyword=keyword, city=city_code)
        cached = search_cache.get(key)
        if cached is not None:
            return cached[:limit]

        # 抓取
        results = self._search_api(keyword, city_code, limit)

        # 缓存成功结果
        if results and not (len(results) == 1 and results[0].get("error")):
            search_cache.set(key, results)

        return results[:limit]

    def get_detail(self, url: str) -> dict[str, Any]:
        """获取岗位详情。"""
        if "zhipin.com" not in url:
            return {"error": f"非 BOSS 直聘 URL: {url}"}

        # 查缓存
        detail_cache = self._make_cache("detail")
        key = self._cache_key(url=url)
        cached = detail_cache.get(key)
        if cached is not None:
            return cached

        # 抓取
        result = self._fetch_detail(url)

        # 缓存成功结果
        if result and not result.get("error"):
            detail_cache.set(key, result)

        return result

    def _search_api(self, keyword: str, city: str, limit: int) -> list[dict[str, Any]]:
        """通过 API 搜索岗位。"""
        if not has_valid_cookies():
            return [{"error": (
                "需要登录 BOSS 直聘。请在 career-kit 项目目录运行：\n"
                "    python -m src.scrapers.boss.login\n"
                "按提示在浏览器完成扫码后回车即可；cookies 保存后长期有效（过期时重跑一次）。"
            )}]

        cookies = load_cookies()
        stoken = get_stoken()
        headers = _build_headers(cookies, stoken)

        params = {
            "scene": "1",
            "query": keyword,
            "city": city,
            "page": "1",
            "pageSize": str(min(limit, 30)),
        }

        try:
            resp = httpx.get(SEARCH_URL, params=params, headers=headers, timeout=15)
            data = resp.json()
        except Exception as e:
            return [{"error": f"请求失败: {e}"}]

        # 处理 code=37（需要计算 stoken）
        if data.get("code") == 37:
            new_stoken = handle_code37(data)
            if new_stoken:
                headers = _build_headers(cookies, new_stoken)
                try:
                    resp = httpx.get(SEARCH_URL, params=params, headers=headers, timeout=15)
                    data = resp.json()
                except Exception as e:
                    return [{"error": f"重试失败: {e}"}]
            else:
                return [{"error": "stoken 计算失败，请安装 iv8: pip install iv8"}]

        # 处理其他错误码
        code = data.get("code")
        if code in (32, 35, 36):
            return [{"error": f"BOSS 风控限制 (code={code})，请稍后重试"}]
        if code != 0:
            return [{"error": f"API 错误: {data.get('message', '')}"}]

        # 提取职位列表
        job_list = (data.get("zpData") or {}).get("jobList", [])
        if not job_list:
            return [{"error": "未找到相关岗位", "keyword": keyword}]

        return [_map_job(job) for job in job_list[:limit]]

    def _fetch_detail(self, url: str) -> dict[str, Any]:
        """获取岗位详情。"""
        if not has_valid_cookies():
            return {"error": (
                "需要登录 BOSS 直聘。请在本项目目录运行：python -m src.scrapers.boss.login"
            )}

        cookies = load_cookies()
        stoken = get_stoken()
        headers = _build_headers(cookies, stoken)

        try:
            resp = httpx.get(url, headers=headers, timeout=15)
            html = resp.text
        except Exception as e:
            return {"error": f"请求失败: {e}"}

        result = _parse_detail_html(html)
        result["url"] = url

        if not result.get("description"):
            return {"error": "未找到岗位详情", "url": url}

        return result