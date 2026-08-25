# 企业 Scraper 贡献指南

感谢你为 Career Kit 企业库贡献代码！

## 快速开始（5 分钟）

### 1. 复制模板

```bash
cp -r src/scrapers/_template src/scrapers/{company_name}
```

### 2. 修改 scraper.py

只需关注 3 处：

```python
class Scraper(CompanyScraper):
    COMPANY_SLUG = "company_en"  # 英文标识，用于缓存目录和日志
    BASE_URL = "https://..."     # 官网

    def search(self, **kwargs) -> list[dict]:
        """搜索岗位 — 实现抓取逻辑"""
        ...

    def get_detail(self, url: str) -> dict:
        """获取详情 — 实现抓取逻辑"""
        ...
```

**框架自动处理**：
- 缓存：通过 `self._make_cache("search"` 或 `"detail")` 创建缓存实例
- 知识库写入：loader 层自动调用，无需手动
- URL 路由：通过 `supports_url()` 或 config.yaml 的 `url_patterns`
- 输出校验：title 和 url 缺失会自动补全

### 3. 注册配置

在 `src/scrapers/config.yaml` 添加：

```yaml
scrapers:
  {company_name}:
    name: 公司显示名
    module: {company_name}.scraper
    class: Scraper
    description: 一句话描述
    url_patterns:
      - "jobs.example.com"    # 用于 URL 路由匹配
    params:
      keyword:
        description: 搜索关键词
        required: false
      city:
        description: 城市名
        required: false
```

### 4. 提交 PR

```bash
git add src/scrapers/{company_name}/
git commit -m "feat: 添加 {公司名} scraper"
git push
```

## 缓存使用

框架提供统一的缓存机制，scraper 无需自己实现：

```python
def search(self, **kwargs):
    # 1. 创建缓存实例（框架自动管理目录和 TTL）
    search_cache = self._make_cache("search")

    # 2. 查缓存
    key = self._cache_key(keyword=kwargs.get("keyword", ""))
    cached = search_cache.get(key)
    if cached is not None:
        return cached

    # 3. 抓取数据
    results = self._fetch_jobs(**kwargs)

    # 4. 缓存成功结果（知识库写入由 loader 自动处理）
    if results and "error" not in results[0]:
        search_cache.set(key, results)

    return results
```

TTL 可通过类变量调整：

```python
class Scraper(CompanyScraper):
    search_cache_ttl = 3600   # 搜索结果 1 小时（默认）
    detail_cache_ttl = 86400  # 详情 24 小时（默认）
```

## 抓取方式选择

根据目标网站选择合适的抓取方式(实现不需要追求优雅，欢迎您的任何提交)：

### 方式 1：httpx 直调 API（推荐）

适用于拿到 API 的网站。

```python
def _fetch_jobs(self, keyword, city, limit):
    resp = httpx.get(
        f"{self.BASE_URL}/api/jobs",
        params={"keyword": keyword, "city": city, "limit": limit},
        headers={"User-Agent": "Mozilla/5.0 ..."},
    )
    data = resp.json()
    return self._format_jobs(data)
```

**优点**：简单快速，无需浏览器
**缺点**：可能有签名验证

### 方式 2：Playwright XHR 拦截

适用于 SPA 页面（React/Vue），或有签名验证的 API。

```python
def _fetch_jobs(self, keyword, city, limit):
    from playwright.sync_api import sync_playwright

    captured = []

    def handle_response(response):
        if "/api/jobs" not in response.url:
            return
        try:
            data = response.json()
            captured.extend(data.get("jobs", []))
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("response", handle_response)

        url = f"{self.BASE_URL}/jobs?keyword={keyword}&city={city}"
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        browser.close()

    return self._format_jobs(captured)
```

**优点**：能处理 SPA 和签名验证
**缺点**：需要 Playwright，速度较慢

### 方式 3：httpx + HTML 解析

适用于传统服务端渲染网站。

```python
def _fetch_jobs(self, keyword, city, limit):
    from bs4 import BeautifulSoup

    resp = httpx.get(
        f"{self.BASE_URL}/jobs",
        params={"keyword": keyword, "city": city},
    )
    soup = BeautifulSoup(resp.text, "html.parser")

    jobs = []
    for item in soup.select(".job-item"):
        jobs.append({
            "title": item.select_one(".title").text.strip(),
            "url": item.select_one("a")["href"],
            "company": self.COMPANY_NAME,
            "location": item.select_one(".location").text.strip(),
        })

    return self._format_jobs(jobs)
```

**优点**：无需 Playwright
**缺点**：HTML 结构变化时需维护

## 标准输出格式

### search() 返回格式

```python
[
    {
        "title": "AI Agent 开发工程师",      # 必填（缺失自动补 "未知岗位"）
        "url": "https://...",               # 必填（缺失自动补空字符串）
        "company": "字节跳动",               # 建议（loader 自动补充）
        "location": "北京、上海",            # 建议
        "summary": "负责 AI Agent 开发...",  # 建议
        "salary": "30-60k",                 # 可选
        "department": "抖音",               # 可选
    }
]
```

### get_detail() 返回格式

```python
{
    "title": "AI Agent 开发工程师",
    "company": "字节跳动",
    "location": "北京",
    "salary": "30-60k",
    "description": "岗位描述全文...",
    "requirements": "任职要求全文...",
    "benefits": "福利待遇...",
    "url": "https://...",
}
```

## 反爬注意事项

1. **User-Agent**：设置真实的浏览器 UA
2. **请求间隔**：每次请求间隔 1-3 秒
3. **随机化**：viewport、UA 等参数随机化
4. **代理**：可选，高频抓取时建议使用
5. **缓存**：利用框架提供的 `self._make_cache()` 方法，避免重复抓取

## 测试

提交 PR 前，请确保：

```bash
# 运行测试
python -m pytest tests/test_scrapers.py -v

# 手动测试
python -c "
from src.scrapers.loader import search_company_jobs
result = search_company_jobs('{company_name}', keyword='Python')
print(f'找到 {result[\"count\"]} 个岗位')
"
```

## 常见问题

### Q: 如何处理登录态？

A: 使用 Cookie 方式。参考小红书 scraper 的实现。

### Q: 如何处理验证码？

A: 目前不支持自动验证码。建议：
1. 降低抓取频率
2. 使用代理
3. 手动处理（扫码登录后保存 Cookie）

### Q: 如何处理反爬？

A: 参考字节跳动 scraper 的反检测措施：
1. 随机化 viewport、UA
2. 注入反检测脚本
3. 模拟人类行为（随机延时、滚动）

### Q: 数据自动保存到哪里？

A: 框架自动将抓取结果保存到 `dev/knowledge/jds/{company_name}/`，无需手动处理。

---

感谢你的贡献！
