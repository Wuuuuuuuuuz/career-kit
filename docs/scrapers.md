# 企业库

> Career Kit 已收录的企业数据源

## 已收录企业

| ID | 名称 | 数据类型 | 状态 | 使用教程 |
|----|------|----------|------|----------|
| `boss` | BOSS直聘 | JD（含薪资） | 可用 | [guide](../src/scrapers/boss/guide.md) |
| `bytedance` | 字节跳动 | JD（社招/校招） | 可用 | [guide](../src/scrapers/bytedance/guide.md) |
| `nowcoder` | 牛客网 | 面经 | 可用 | [guide](../src/scrapers/nowcoder/guide.md) |

> 教程的唯一事实源是各 scraper 包内的 `guide.md`，LLM 运行时通过
> `get_scraper_guide(company)` 工具按需读取同一文件。新增企业时在包内附
> guide.md 即自动生效（模板见 `_template/guide.md`）。

## 使用流程

```
1. list_company_jobs()                    # 查看可用企业和参数
2. fetch_company_jobs(company="boss", params='{"keyword":"Python"}')  # 搜索岗位
3. fetch_jd_detail(url="https://...")     # 获取详情
```

## 通用参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `keyword` | 搜索关键词 | `"Python"`, `"AI Agent"` |
| `city` | 城市名 | `"上海"`, `"北京"` |
| `limit` | 返回数量上限 | `10`, `20` |

## 数据用途

| 数据类型 | 用途 | 使用场景 |
|----------|------|----------|
| JD | 了解岗位要求 | 差距分析、路线图规划 |
| 面经 | 了解面试内容 | 面试准备、技能补充 |
| 薪资 | 了解市场行情 | 目标设定、期望管理 |

## 贡献新 Scraper

详见 [CONTRIBUTING.md](../src/scrapers/CONTRIBUTING.md)
