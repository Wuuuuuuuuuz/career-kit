# 企业库

> Career Kit 已收录的企业数据源

## 已收录企业

| ID | 名称 | 数据类型 | 状态 | 文档 |
|----|------|----------|------|------|
| `boss` | BOSS直聘 | JD | 可用 | [BOSS直聘文档](scrapers/boss.md) |
| `bytedance` | 字节跳动 | JD | 可用 | [字节跳动文档](scrapers/bytedance.md) |
| `nowcoder` | 牛客网 | 面经 | 可用 | [牛客网文档](scrapers/nowcoder.md) |

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
