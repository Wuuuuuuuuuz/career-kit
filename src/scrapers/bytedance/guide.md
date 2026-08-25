# 字节跳动 使用指南

## 用途

搜索字节跳动官方招聘网站（jobs.bytedance.com）的岗位数据，支持社招和校招。无需登录。

## 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| keyword | 否 | 搜索关键词，如 `"Python"`、`"AI Agent"` |
| city | 否 | 城市名，如 `"北京"`、`"上海"`、`"深圳"` |
| job_type | 否 | 岗位类别：研发 / 运营 / 产品 / 销售 / 设计 / 市场 / 游戏策划 / 教研教学 |
| portal | 否 | `experienced`=社招（默认），`campus`=校招 |
| limit | 否 | 返回数量上限，默认 20 |

## 调用示例

```
fetch_company_jobs(company="bytedance", params='{"keyword":"AI Agent", "portal":"campus", "limit":10}')
```

## 返回字段

| 字段 | 说明 |
|------|------|
| title | 岗位名称 |
| url | 详情页链接（可传给 fetch_jd_detail） |
| location | 工作地点 |
| department | 所属类目 |
| summary | 岗位摘要 |
| recruit_type | 社招 / 校招 / 实习 |

## 注意事项

1. **salary 通常为空**——字节不公开薪资，薪资行情请用 BOSS直聘源
2. 校招岗位记得加 `"portal":"campus"`
3. 详情全文（JD 描述 + 任职要求）用 `fetch_jd_detail(url=...)` 获取
