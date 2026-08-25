"""字节跳动招聘 Scraper——通过 Playwright 拦截 XHR + httpx 直调详情 API。"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ..base import CompanyScraper

# 城市名称 → 代码映射（常用）
CITY_MAP: dict[str, str] = {
    "北京": "CT_11", "上海": "CT_125", "深圳": "CT_128", "杭州": "CT_52",
    "成都": "CT_22", "广州": "CT_118", "西安": "CT_15", "武汉": "CT_17",
    "南京": "CT_72", "重庆": "CT_4", "郑州": "CT_85", "长沙": "CT_60",
    "天津": "CT_130", "厦门": "CT_126", "合肥": "CT_66", "苏州": "CT_119",
    "青岛": "CT_83", "济南": "CT_68", "大连": "CT_10", "珠海": "CT_133",
    "福州": "CT_44", "昆明": "CT_70", "沈阳": "CT_122", "哈尔滨": "CT_55",
    "贵阳": "CT_53", "东莞": "CT_38", "无锡": "CT_145", "南昌": "CT_75",
    "石家庄": "CT_124", "南宁": "CT_78", "宁波": "CT_80", "温州": "CT_143",
    "海口": "CT_54", "长春": "CT_12", "烟台": "CT_156", "徐州": "CT_152",
    "洛阳": "CT_73", "绍兴": "CT_117", "佛山": "CT_43", "惠州": "CT_57",
    "太原": "CT_129", "呼和浩特": "CT_56", "金华": "CT_63", "兰州": "CT_71",
    "乌鲁木齐": "CT_141", "新加坡": "CT_163", "东京": "CT_275", "首尔": "CT_316",
    "伦敦": "CT_215", "纽约": "CT_260", "圣何塞": "CT_311", "西雅图": "CT_310",
}

# 岗位类别名称 → ID 映射
JOB_TYPE_MAP: dict[str, str] = {
    "研发": "6704215862603155720", "运营": "6704215882479962371",
    "产品": "6704215864629004552", "销售": "6709824272505768200",
    "职能": "6704215913488451847", "职能/支持": "6704215913488451847",
    "设计": "6709824272514156812", "市场": "6704215901438216462",
    "游戏策划": "6850051244971526414", "教研教学": "6794746007419619592",
}

BASE_URL = "https://jobs.bytedance.com"
DETAIL_API = f"{BASE_URL}/api/v1/job/posts/{{job_id}}"


class Scraper(CompanyScraper):
    """字节跳动招聘 Scraper。

    search: Playwright 加载页面 → 拦截 XHR → 提取搜索结果
    get_detail: httpx 直调详情 API（无需签名）
    缓存: 搜索结果 1 小时，详情 24 小时
    知识库写入: 由 loader 自动处理
    """

    COMPANY_SLUG = "bytedance"

    def supports_url(self, url: str) -> bool:
        return "jobs.bytedance.com" in url

    def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        """搜索字节跳动岗位。先查缓存，未命中再抓取。"""
        keyword = kwargs.get("keyword", "")
        city = kwargs.get("city", "")
        job_type = kwargs.get("job_type", "")
        portal = kwargs.get("portal", "experienced")
        limit = kwargs.get("limit", 20)

        # 查缓存（统一走 base 的 data/cache/ 目录约定）
        search_cache = self._make_cache("search")
        key = self._cache_key(keyword=keyword, city=city, job_type=job_type, portal=portal)
        cached = search_cache.get(key)
        if cached is not None:
            return cached[:limit]

        # 抓取
        results = self._search_via_playwright(
            keyword=keyword, city=city, job_type=job_type,
            portal=portal, limit=limit,
        )

        # 缓存成功结果（知识库写入由 loader 自动处理）
        if results and "error" not in results[0]:
            search_cache.set(key, results)

        return results

    def get_detail(self, url: str) -> dict[str, Any]:
        """获取岗位详情。先查缓存，未命中再调 API。"""
        job_id = self._extract_job_id(url)
        if not job_id:
            return {"error": f"无法从 URL 提取 job_id: {url}"}

        # 查缓存
        detail_cache = self._make_cache("detail")
        key = self._cache_key(job_id=job_id)
        cached = detail_cache.get(key)
        if cached is not None:
            return cached

        portal_type = "1" if "/campus/" in url else "2"
        api_url = DETAIL_API.format(job_id=job_id)

        try:
            resp = httpx.get(
                api_url,
                params={"portal_type": portal_type, "with_recommend": "false"},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Referer": f"{BASE_URL}/experienced/position" if portal_type == "2" else f"{BASE_URL}/campus/position",
                    "Origin": BASE_URL,
                },
                timeout=15,
                follow_redirects=True,
            )
            data = resp.json()
        except Exception as e:
            return {"error": f"请求详情 API 失败: {e}"}

        if data.get("code") != 0:
            return {"error": f"API 返回错误: {data.get('msg', data)}"}

        detail = data.get("data", {}).get("job_post_detail", {})
        if not detail:
            return {"error": "API 返回空数据"}

        result = self._format_detail(detail, url)

        # 缓存成功结果（知识库写入由 loader 自动处理）
        if "error" not in result:
            detail_cache.set(key, result)

        return result

    # === 内部方法 ===

    def _search_via_playwright(self, **params: Any) -> list[dict[str, Any]]:
        """通过 Playwright 拦截 XHR 获取搜索结果。"""
        import os
        import random
        from playwright.sync_api import sync_playwright
        from urllib.parse import quote

        # 清除代理环境变量
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            os.environ.pop(k, None)

        keyword = params["keyword"]
        city = params["city"]
        job_type = params["job_type"]
        portal = params["portal"]
        limit = params["limit"]

        city_code = CITY_MAP.get(city, "")
        type_id = JOB_TYPE_MAP.get(job_type, "")

        # 构建 URL（校招/社招参数名不同）
        if portal == "campus":
            url_params = {
                "keywords": keyword or "",
                "category": type_id or "",
                "location": city_code or "",
                "project": "", "type": "", "job_hot_flag": "",
                "current": "1", "limit": "10",
                "functionCategory": "", "tag": "",
            }
            qs = "&".join(f"{k}={quote(v)}" for k, v in url_params.items())
            target_url = f"{BASE_URL}/campus/position?{qs}"
        else:
            url_params = {
                "keyword": keyword or "",
                "limit": "10", "offset": "0",
                "job_category_id_list": type_id or "",
                "tag_id_list": "", "location_code_list": city_code or "",
                "subject_id_list": "", "recruitment_id_list": "",
                "portal_type": "2", "job_function_id_list": "",
                "storefront_id_list": "", "portal_entrance": "1",
            }
            qs = "&".join(f"{k}={v}" for k, v in url_params.items())
            target_url = f"{BASE_URL}/experienced/position?{qs}"

        captured_data: dict[str, Any] = {"posts": [], "total": 0}

        def handle_response(response):
            """拦截搜索 API 的 XHR 响应。"""
            url = response.url
            if "/api/v1/search/job/posts" not in url:
                return
            try:
                body = response.json()
                if body.get("code") == 0 and "data" in body:
                    data = body["data"]
                    captured_data["total"] = data.get("count", 0)
                    posts = data.get("job_post_list", [])
                    captured_data["posts"].extend(posts)
            except Exception:
                pass

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    channel="msedge",
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--no-proxy-server",
                    ],
                    proxy={"server": "direct://"},
                )
                # 随机化 viewport 和 user-agent
                viewports = [
                    {"width": 1920, "height": 1080},
                    {"width": 1366, "height": 768},
                    {"width": 1536, "height": 864},
                    {"width": 1440, "height": 900},
                ]
                ua_list = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                ]
                context = browser.new_context(
                    user_agent=random.choice(ua_list),
                    viewport=random.choice(viewports),
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                )
                # 注入反检测脚本
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
                    window.chrome = {runtime: {}};
                """)
                page = context.new_page()
                page.on("response", handle_response)

                # 模拟人类行为：先访问首页再跳转
                page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(random.randint(1000, 2000))

                # 导航到搜索页
                page.goto(target_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(random.randint(1500, 3000))

                # 关闭可能的遮罩层
                try:
                    mask_close = page.locator('[class*="guide"] [class*="close"], [class*="mask"] [class*="close"]')
                    if mask_close.count() > 0 and mask_close.first.is_visible():
                        mask_close.first.click(timeout=2000)
                        page.wait_for_timeout(500)
                except Exception:
                    pass

                # 仅在明确请求多页时翻页（默认不翻页，避免触发反爬）
                if limit > 10:
                    total = captured_data["total"]
                    pages_needed = min((total + 9) // 10, (limit + 9) // 10, 6)  # 最多翻 5 页
                    for page_num in range(1, pages_needed):
                        if len(captured_data["posts"]) >= limit:
                            break
                        try:
                            next_btn = page.locator('[class*="pagination"] [class*="next"]').first
                            if next_btn.is_visible() and next_btn.is_enabled():
                                page.wait_for_timeout(random.randint(800, 1500))
                                next_btn.click()
                                page.wait_for_timeout(random.randint(2000, 3000))
                            else:
                                break
                        except Exception:
                            break

                browser.close()
        except Exception as e:
            return [{"error": f"Playwright 执行失败: {e}"}]

        if not captured_data["posts"]:
            return [{"error": "未能拦截到搜索 API 响应"}]

        captured_data["portal"] = portal
        return self._format_search_results(captured_data, limit)

    def _format_search_results(self, data: dict, limit: int) -> list[dict[str, Any]]:
        """格式化搜索结果。"""
        posts = data.get("posts", [])
        total = data.get("total", len(posts))
        portal = data.get("portal", "experienced")
        portal_path = "campus" if portal == "campus" else "experienced"

        results = []
        for post in posts[:limit]:
            city_info = post.get("city_info", {})
            job_cat = post.get("job_category", {})
            recruit = post.get("recruit_type", {})

            cities = [c.get("name", "") for c in post.get("city_list", [])]
            location = "、".join(cities) if cities else city_info.get("name", "")

            results.append({
                "title": post.get("title", ""),
                "url": f"{BASE_URL}/{portal_path}/position/{post.get('id', '')}/detail",
                "company": "字节跳动",
                "location": location,
                "department": job_cat.get("name", ""),
                "summary": self._truncate(post.get("description", ""), 200),
                "job_id": post.get("id", ""),
                "job_code": post.get("code", ""),
                "recruit_type": recruit.get("name", ""),
                "publish_time": post.get("publish_time", 0),
            })

        # 在第一个结果中附加 total 信息
        if results:
            results[0]["_total"] = total

        return results

    def _format_detail(self, detail: dict, url: str) -> dict[str, Any]:
        """格式化岗位详情。"""
        city_info = detail.get("city_info", {})
        cities = [c.get("name", "") for c in detail.get("city_list", [])]
        location = "、".join(cities) if cities else city_info.get("name", "")

        job_cat = detail.get("job_category", {})
        parent_cat = job_cat.get("parent", {})
        category = f"{parent_cat.get('name', '')} - {job_cat.get('name', '')}" if parent_cat.get("name") else job_cat.get("name", "")

        recruit = detail.get("recruit_type", {})
        parent_recruit = recruit.get("parent", {})

        return {
            "title": detail.get("title", ""),
            "company": "字节跳动",
            "location": location,
            "salary": "",  # 字节不公开薪资
            "description": detail.get("description", ""),
            "requirements": detail.get("requirement", ""),
            "benefits": "",
            "category": category,
            "recruit_type": recruit.get("name", ""),
            "portal_type": parent_recruit.get("name", ""),
            "job_code": detail.get("code", ""),
            "job_id": detail.get("id", ""),
            "url": url,
        }

    @staticmethod
    def _extract_job_id(url: str) -> str | None:
        """从 URL 提取 job_id。"""
        m = re.search(r"/position/(\d+)/", url)
        return m.group(1) if m else None

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """截断文本。"""
        text = text.replace("\n", " ").strip()
        return text[:max_len] + "..." if len(text) > max_len else text

