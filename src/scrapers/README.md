# 企业库

社区驱动的企业招聘数据源集合。

## 已注册企业

| ID | 名称 | 数据类型 | 说明 |
|----|------|----------|------|
| `boss` | BOSS直聘 | JD | 需要登录，详见 [BOSS直聘文档](boss/README.md) |
| `bytedance` | 字节跳动 | JD | 支持社招/校招 |
| `nowcoder` | 牛客网 | 面经 | 面经分享平台 |

## 使用流程

```
1. list_data_sources()           # 查看可用企业和参数
2. fetch_company_jobs(company, params)  # 搜索岗位
3. fetch_jd_detail(url)          # 获取详情
```

## 参数说明

每个 scraper 支持的参数不同，调用 `list_data_sources()` 查看详情。

通用参数：
- `keyword` - 搜索关键词
- `city` - 城市名
- `limit` - 返回数量上限

## 贡献新 Scraper

详见 [CONTRIBUTING.md](CONTRIBUTING.md)