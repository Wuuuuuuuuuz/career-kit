"""牛客网面经 Scraper——Playwright DOM 抓取搜索结果 + 详情页内容。

数据类型：面经（interviews），写入 dev/knowledge/interviews/nowcoder/

搜索策略：
- URL: https://www.nowcoder.com/search/all?query={query}&type=all&subType=818
- subType=818 是面经筛选参数，过滤掉非面经内容
- 从搜索结果页 DOM 提取 discuss URL 列表
- 返回标题/URL/摘要给 LLM，由 LLM 决定哪些需要查看详情

详情策略：
- 直接访问 discuss 页面
- 从 `.nc-slate-editor-content` 提取全文（SSR 渲染，无需登录）

WAF 说明：gw-c.nowcoder.com 有阿里云 WAF，需真实浏览器指纹才能通过。
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from ..base import CompanyScraper

SEARCH_URL = "https://www.nowcoder.com/search/all?query={query}&type=all&subType=818"


class Scraper(CompanyScraper):
    """牛客网面经 Scraper。

    search: Playwright 打开搜索页 → DOM 提取面经列表 → 返回标题/URL
    get_detail: Playwright 访问详情页 → 提取 .nc-slate-editor-content 全文
    缓存: 搜索结果 1 小时，详情 24 小时
    知识库写入: 面经格式，写入 interviews/nowcoder/
    """

    COMPANY_SLUG = "nowcoder"
    DATA_TYPE = "interviews"

    # 搜索参数定义（唯一事实源，list_data_sources 渲染给 LLM）
    PARAMS: dict[str, dict[str, Any]] = {
        "keyword": {"required": False, "description": "搜索关键词（如 \"Agent 开发\"、\"面经\"）"},
        "filter_company": {"required": False, "description": "按公司筛选（如 \"字节跳动\"、\"腾讯\"），自动拼接到搜索词"},
        "is_intern": {"required": False, "description": "是否搜索实习岗位（true 时追加\"实习\"关键词）"},
        "order": {"required": False, "description": "排序方式：create=最新(默认), quality=最热"},
        "page": {"required": False, "description": "页码，默认 1"},
        "limit": {"required": False, "description": "返回数量上限，默认 20"},
    }

    search_cache_ttl = 3600
    detail_cache_ttl = 86400

    def __init__(self, cookie: str = ""):
        self._cookie = cookie

    def supports_url(self, url: str) -> bool:
        return "nowcoder.com" in url

    def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        """搜索牛客网面经。

        Args:
            keyword: 搜索关键词（如 "AI Agent"、"面经"）
            filter_company: 公司名（如 "字节跳动"），会拼接到搜索词中
            is_intern: 是否搜索实习（True 时追加 "实习" 关键词）
            order: 排序方式（create=最新, quality=最热）
            page: 页码
            limit: 返回数量上限
        """
        keyword = kwargs.get("keyword", "")
        company = kwargs.get("filter_company", "")
        is_intern = kwargs.get("is_intern", False)
        order = kwargs.get("order", "create")
        page = kwargs.get("page", 1)
        limit = kwargs.get("limit", 20)

        # 构造搜索词：公司 + 关键词 + 实习/开发
        parts = []
        if company and company not in keyword:
            parts.append(company)
        if keyword:
            parts.append(keyword)
        if is_intern and "实习" not in keyword:
            parts.append("实习")

        query = " ".join(parts).strip()
        if not query:
            return [{"error": "搜索关键词不能为空"}]

        # 查缓存
        search_cache = self._make_cache("search")
        key = self._cache_key(query=query, order=order, page=page)
        cached = search_cache.get(key)
        if cached is not None:
            return cached[:limit]

        # Playwright DOM 抓取
        results = self._search_via_playwright(query=query, order=order, page=page, limit=limit)

        # 缓存成功结果
        if results and not (len(results) == 1 and results[0].get("error")):
            search_cache.set(key, results)

        return results[:limit]

    def get_detail(self, url: str) -> dict[str, Any]:
        """获取面经详情全文。"""
        if "nowcoder.com" not in url:
            return {"error": f"非牛客网 URL: {url}"}

        # 查缓存
        detail_cache = self._make_cache("detail")
        key = self._cache_key(url=url)
        cached = detail_cache.get(key)
        if cached is not None:
            return cached

        # Playwright 抓取详情页
        result = self._fetch_detail_via_playwright(url)

        # 缓存成功结果
        if result and not result.get("error"):
            detail_cache.set(key, result)

        return result

    # === Playwright 方法 ===

    def _launch_browser(self):
        """启动 Playwright 浏览器，使用系统 Edge。"""
        import os
        # 清除代理环境变量，避免 SOCKS5 代理干扰浏览器连接
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            os.environ.pop(k, None)

        from playwright.sync_api import sync_playwright
        p = sync_playwright().start()
        browser = p.chromium.launch(
            headless=True,
            channel="msedge",
            args=["--disable-blink-features=AutomationControlled", "--no-proxy-server"],
            proxy={"server": "direct://"},
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
        """通过 Playwright DOM 抓取搜索结果页。"""
        search_url = SEARCH_URL.format(query=quote(query))
        if page > 1:
            search_url += f"&page={page}"

        try:
            p, browser, context = self._launch_browser()
            page_obj = context.new_page()

            page_obj.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            page_obj.wait_for_timeout(3000)  # 等待 JS 渲染

            # 从 DOM 提取搜索结果
            results = page_obj.evaluate("""
                () => {
                    const items = [];
                    // 搜索结果卡片的链接
                    const links = document.querySelectorAll('a[href*="/discuss/"]');
                    for (const link of links) {
                        const href = link.getAttribute('href');
                        if (!href || !href.includes('/discuss/')) continue;

                        // 找到最近的父容器获取标题和摘要
                        const container = link.closest('.nc-search-result-item')
                            || link.closest('.search-result-item')
                            || link.closest('[class*="search"]')
                            || link.parentElement?.parentElement;

                        // 标题：链接文本或容器内的标题元素
                        let title = link.textContent?.trim() || '';
                        if (!title && container) {
                            const titleEl = container.querySelector('h3, h2, .title, [class*="title"]');
                            title = titleEl?.textContent?.trim() || '';
                        }

                        // 摘要：容器内的描述文本
                        let snippet = '';
                        if (container) {
                            const descEl = container.querySelector('.content, .desc, [class*="content"], [class*="desc"], [class*="summary"]');
                            if (descEl && descEl !== link) {
                                snippet = descEl.textContent?.trim() || '';
                            }
                        }

                        // 构造完整 URL
                        const fullUrl = href.startsWith('http') ? href : 'https://www.nowcoder.com' + href;

                        // 避免重复
                        if (!items.find(i => i.url === fullUrl) && title) {
                            items.push({
                                title: title.substring(0, 200),
                                url: fullUrl,
                                snippet: snippet.substring(0, 300),
                            });
                        }
                    }
                    return items;
                }
            """)

            browser.close()
            p.stop()
        except Exception as e:
            return [{"error": f"Playwright 执行失败: {e}"}]

        if not results:
            return [{"error": "未找到相关面经", "query": query}]

        # 格式化结果
        formatted = []
        for item in results[:limit]:
            title = item.get("title", "")
            company = self._extract_company(title)
            position = self._extract_position(title)

            formatted.append({
                "title": title,
                "url": item["url"],
                "company": company,
                "position": position,
                "snippet": item.get("snippet", ""),
                "source": "nowcoder",
            })

        return formatted

    def _fetch_detail_via_playwright(self, url: str) -> dict[str, Any]:
        """通过 Playwright 访问详情页，从 DOM 提取面经全文。"""
        try:
            p, browser, context = self._launch_browser()
            page_obj = context.new_page()

            page_obj.goto(url, wait_until="domcontentloaded", timeout=30000)
            page_obj.wait_for_timeout(2000)

            # 从 DOM 提取内容
            data = page_obj.evaluate("""
                () => {
                    // 标题：优先 h1
                    const h1 = document.querySelector('h1');
                    const title = h1?.textContent?.trim() || '';

                    // 正文内容
                    const contentEl = document.querySelector('.nc-slate-editor-content')
                        || document.querySelector('.post-content-box');
                    const content = contentEl?.textContent?.trim() || '';

                    // 作者
                    const authorEl = document.querySelector('.content-user-info .name');
                    const author = authorEl?.textContent?.trim() || '';

                    return { title, content, author };
                }
            """)

            browser.close()
            p.stop()
        except Exception as e:
            return {"error": f"详情页抓取失败: {e}"}

        if not data or not data.get("content"):
            return {"error": "未找到面经内容", "url": url}

        title = data.get("title", "")
        content = data.get("content", "")
        company = self._extract_company(title + content)
        position = self._extract_position(title + content)
        round_name = self._extract_round(title + content)

        return {
            "title": title or self._extract_title_from_content(content),
            "company": company,
            "position": position,
            "round": round_name,
            "content": content,
            "source": "nowcoder",
            "url": url,
            "date": "",
            "author": data.get("author", ""),
        }

    # === 提取方法 ===

    @staticmethod
    def _extract_company(text: str) -> str:
        companies = [
            "字节跳动", "字节", "腾讯", "阿里", "阿里巴巴", "百度", "美团", "京东",
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
    def _extract_position(text: str) -> str:
        position_keywords = [
            "前端", "后端", "客户端", "服务端", "全栈",
            "Java", "Python", "Go", "C++", "Rust",
            "算法", "机器学习", "深度学习", "AI", "Agent", "NLP", "CV",
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
    def _extract_title_from_content(content: str) -> str:
        if not content:
            return "无标题"
        first_line = content.split("\n")[0].strip()
        first_line = re.sub(r'^#+\s*', '', first_line)
        if len(first_line) > 80:
            first_line = first_line[:80] + "..."
        return first_line or "无标题"
