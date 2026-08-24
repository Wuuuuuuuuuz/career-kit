"""牛客网面经 Scraper——Playwright 拦截 XHR 获取搜索结果。

数据类型：面经（interviews），写入 dev/knowledge/interviews/nowcoder/
参考实现：Crawl4NK (https://github.com/z0l0y/Crawl4NK)

API 端点（经浏览器验证）：
- 搜索：POST https://gw-c.nowcoder.com/api/sparta/pc/search
- 详情：GET  https://gw-c.nowcoder.com/api/sparta/detail/{api_type}/detail/{detail_id}

WAF 说明：gw-c.nowcoder.com 有阿里云 WAF，需真实浏览器指纹才能通过。
"""

from __future__ import annotations

import re
from typing import Any

from ..base import CompanyScraper

# API 端点
SEARCH_API = "https://gw-c.nowcoder.com/api/sparta/pc/search"
DETAIL_API = "https://gw-c.nowcoder.com/api/sparta/detail/{api_type}/detail/{detail_id}"
SEARCH_URL = "https://www.nowcoder.com/search/all?query={query}&type=all"


class Scraper(CompanyScraper):
    """牛客网面经 Scraper。

    search: Playwright 加载搜索页 → 拦截 XHR → 返回面经列表
    get_detail: Playwright 调用详情 API → 返回面经全文
    缓存: 搜索结果 1 小时，详情 24 小时
    知识库写入: 面经格式，写入 interviews/nowcoder/
    """

    COMPANY_SLUG = "nowcoder"
    DATA_TYPE = "interviews"

    search_cache_ttl = 3600
    detail_cache_ttl = 86400

    def __init__(self, cookie: str = ""):
        self._cookie = cookie

    def supports_url(self, url: str) -> bool:
        return "nowcoder.com" in url

    def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        """搜索牛客网面经。"""
        keyword = kwargs.get("keyword", "")
        company = kwargs.get("company", "")
        order = kwargs.get("order", "create")
        page = kwargs.get("page", 1)
        limit = kwargs.get("limit", 20)

        query = keyword
        if company and company not in keyword:
            query = f"{company} {keyword}" if keyword else company

        if not query.strip():
            return [{"error": "搜索关键词不能为空"}]

        # 查缓存
        search_cache = self._make_cache("search")
        key = self._cache_key(query=query, order=order, page=page)
        cached = search_cache.get(key)
        if cached is not None:
            return cached[:limit]

        # 抓取
        results = self._search_via_playwright(query=query, order=order, page=page, limit=limit)

        # 缓存成功结果
        if results and not (len(results) == 1 and results[0].get("error")):
            search_cache.set(key, results)

        return results[:limit]

    def get_detail(self, url: str) -> dict[str, Any]:
        """获取面经详情。"""
        detail_id, api_type = self._parse_url(url)
        if not detail_id:
            return {"error": f"无法从 URL 提取 ID: {url}"}

        # 查缓存
        detail_cache = self._make_cache("detail")
        key = self._cache_key(detail_id=detail_id, api_type=api_type)
        cached = detail_cache.get(key)
        if cached is not None:
            return cached

        # 抓取详情
        result = self._fetch_detail_via_playwright(detail_id, api_type, url)

        # 缓存成功结果
        if result and not result.get("error"):
            detail_cache.set(key, result)

        return result

    # === Playwright 方法 ===

    def _launch_browser(self):
        """启动 Playwright 浏览器，使用系统 Edge。"""
        from playwright.sync_api import sync_playwright
        p = sync_playwright().start()
        browser = p.chromium.launch(
            headless=True,
            channel="msedge",
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-CN",
        )
        # 反检测
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        return p, browser, context

    def _search_via_playwright(self, query: str, order: str, page: int, limit: int) -> list[dict[str, Any]]:
        """通过 Playwright 拦截 XHR 获取搜索结果。"""
        from urllib.parse import quote

        captured_records: list[dict] = []

        def handle_response(response):
            """拦截搜索 API 的 XHR 响应。"""
            if SEARCH_API not in response.url:
                return
            try:
                body = response.json()
                if body.get("success") and "data" in body:
                    records = body["data"].get("records", [])
                    captured_records.extend(records)
            except Exception:
                pass

        search_url = SEARCH_URL.format(query=quote(query))

        try:
            p, browser, context = self._launch_browser()
            page_obj = context.new_page()
            page_obj.on("response", handle_response)

            # 访问搜索页（会触发 XHR）
            page_obj.goto(search_url, wait_until="networkidle", timeout=30000)
            page_obj.wait_for_timeout(2000)

            browser.close()
            p.stop()
        except Exception as e:
            return [{"error": f"Playwright 执行失败: {e}"}]

        if not captured_records:
            return [{"error": "未能拦截到搜索 API 响应"}]

        # 解析结果
        results = []
        for record in captured_records:
            item = self._parse_search_record(record)
            if item:
                results.append(item)
            if len(results) >= limit:
                break

        return results

    def _fetch_detail_via_playwright(self, detail_id: str, api_type: str, url: str) -> dict[str, Any]:
        """通过 Playwright 调用详情 API。"""
        api_url = DETAIL_API.format(api_type=api_type, detail_id=detail_id)
        captured_data: dict = {}

        def handle_response(response):
            if api_url not in response.url and detail_id not in response.url:
                return
            try:
                body = response.json()
                if "data" in body:
                    captured_data["data"] = body["data"]
            except Exception:
                pass

        try:
            p, browser, context = self._launch_browser()
            page_obj = context.new_page()
            page_obj.on("response", handle_response)

            # 先访问首页建立 cookie
            page_obj.goto("https://www.nowcoder.com/", wait_until="domcontentloaded", timeout=15000)
            page_obj.wait_for_timeout(1000)

            # 通过 JS fetch 调用详情 API
            result = page_obj.evaluate("""
                async (apiUrl) => {
                    const resp = await fetch(apiUrl, {
                        headers: {
                            'Accept': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest',
                        }
                    });
                    return await resp.json();
                }
            """, api_url)

            browser.close()
            p.stop()
        except Exception as e:
            return {"error": f"详情 API 请求失败: {e}"}

        detail_data = result.get("data") if result else captured_data.get("data")
        if not detail_data:
            return {"error": "详情 API 返回空数据"}

        return self._format_detail(detail_data, url, api_type)

    # === 解析方法 ===

    def _parse_search_record(self, record: dict) -> dict[str, Any] | None:
        """解析搜索结果中的一条记录。

        API 结构：
        record.data = {contentId, contentType, contentData, userBrief, ...}
        - contentType 250: contentData 有 title/content/uuid
        - contentType 74:  contentData 为空，需详情 API
        """
        record_data = record.get("data", {})
        if not record_data:
            return None

        content_type = record_data.get("contentType", 0)
        content_data = record_data.get("contentData", {})
        user_brief = record_data.get("userBrief", {})
        content_id = record_data.get("contentId", "")

        # 从 userBrief 提取公司和岗位
        identity_list = user_brief.get("identityList") or []
        company = identity_list[0].get("companyName", "") if identity_list else ""
        position = identity_list[0].get("jobName", "") if identity_list else ""

        if content_type == 250 and content_data:
            # moment 类型，数据在 contentData 中
            uuid = content_data.get("uuid", "")
            title = content_data.get("title", "")
            content = content_data.get("content", "")
            created_at = content_data.get("createTime", "")

            if not company:
                company = self._extract_company(title + content)
            if not position:
                position = self._extract_position_from_text(title)

            return {
                "title": title or self._extract_title_from_content(content),
                "url": f"https://www.nowcoder.com/feed/main/detail/{uuid}",
                "company": company,
                "position": position,
                "content": self._truncate(content, 500),
                "source": "nowcoder",
                "detail_id": uuid,
                "api_type": "moment-data",
                "author": user_brief.get("nickname", ""),
                "created_time": self._parse_timestamp(created_at),
            }
        elif content_type == 74:
            # discuss 类型，contentData 为空，用 contentId 构造 URL
            return {
                "title": record.get("title") or f"面经 #{content_id}",
                "url": f"https://www.nowcoder.com/discuss/{content_id}",
                "company": company,
                "position": position,
                "content": "",
                "source": "nowcoder",
                "detail_id": str(content_id),
                "api_type": "content-data",
                "author": user_brief.get("nickname", ""),
                "created_time": "",
            }
        else:
            # 未知类型，尝试通用解析
            title = content_data.get("title", "") if content_data else ""
            return {
                "title": title or f"帖子 #{content_id}",
                "url": f"https://www.nowcoder.com/discuss/{content_id}",
                "company": company,
                "position": position,
                "content": "",
                "source": "nowcoder",
                "detail_id": str(content_id),
                "api_type": "content-data",
                "author": user_brief.get("nickname", ""),
                "created_time": "",
            }

    def _format_detail(self, data: dict, url: str, api_type: str) -> dict[str, Any]:
        """格式化详情数据为标准面经格式。"""
        if api_type == "moment-data":
            moment = data.get("momentData", data)
            content = moment.get("content", "")
            title = moment.get("title", "")
            created_time = moment.get("createTime", "")
            user_brief = data.get("userBrief", {})
        else:
            content_data = data.get("contentData", data)
            content = content_data.get("content", "")
            title = content_data.get("title", "")
            created_time = content_data.get("createTime", "")
            user_brief = data.get("userBrief", {})

        identity_list = user_brief.get("identityList") or []
        company = identity_list[0].get("companyName", "") if identity_list else ""
        position = identity_list[0].get("jobName", "") if identity_list else ""

        if not company:
            company = self._extract_company(title + content)
        if not position:
            position = self._extract_position_from_text(title)

        round_name = self._extract_round(title + content)

        return {
            "title": title or self._extract_title_from_content(content),
            "company": company,
            "position": position,
            "round": round_name,
            "content": content,
            "source": "nowcoder",
            "url": url,
            "date": self._parse_timestamp(created_time),
            "author": user_brief.get("nickname", ""),
        }

    @staticmethod
    def _parse_url(url: str) -> tuple[str, str]:
        """从 URL 解析 detail_id 和 api_type。"""
        m = re.search(r"/discuss/(\d+)", url)
        if m:
            return m.group(1), "content-data"

        m = re.search(r"/detail/([a-f0-9]+)", url)
        if m:
            return m.group(1), "moment-data"

        return "", ""

    @staticmethod
    def _extract_title_from_content(content: str) -> str:
        if not content:
            return "无标题"
        first_line = content.split("\n")[0].strip()
        first_line = re.sub(r'^#+\s*', '', first_line)
        if len(first_line) > 80:
            first_line = first_line[:80] + "..."
        return first_line or "无标题"

    @staticmethod
    def _extract_company(text: str) -> str:
        companies = [
            "字节跳动", "腾讯", "阿里", "阿里巴巴", "百度", "美团", "京东",
            "华为", "小米", "网易", "快手", "拼多多", "滴滴", "bilibili",
            "B站", "小红书", "蚂蚁", "蚂蚁集团", "微软", "Google", "苹果",
            "亚马逊", "Apple", "Meta", "商汤", "旷视", "科大讯飞", "大疆",
            "OPPO", "vivo", "荣耀", "联想", "中兴", "海尔", "比亚迪",
        ]
        for company in companies:
            if company in text:
                return company
        return ""

    @staticmethod
    def _extract_position_from_text(text: str) -> str:
        position_keywords = [
            "前端", "后端", "客户端", "服务端", "全栈",
            "Java", "Python", "Go", "C++", "Rust",
            "算法", "机器学习", "深度学习", "AI", "NLP", "CV",
            "数据", "大数据", "云计算", "安全",
            "产品", "运营", "测试", "运维", "DevOps",
            "Android", "iOS", "嵌入式",
        ]
        for kw in position_keywords:
            if kw.lower() in text.lower():
                return kw
        return ""

    @staticmethod
    def _extract_round(text: str) -> str:
        patterns = [
            r"([一二三四五六])面",
            r"(一面|二面|三面|四面|五面|六面)",
            r"(HR面|hr面|Hr面)",
            r"(终面|终试)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return m.group(1)
        return ""

    @staticmethod
    def _parse_timestamp(ts: Any) -> str:
        if not ts:
            return ""
        try:
            from datetime import datetime
            if isinstance(ts, (int, float)):
                if ts > 1e12:
                    ts = ts / 1000
                return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            return str(ts)[:10]
        except Exception:
            return str(ts)[:10]

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        text = text.replace("\n", " ").strip()
        return text[:max_len] + "..." if len(text) > max_len else text
