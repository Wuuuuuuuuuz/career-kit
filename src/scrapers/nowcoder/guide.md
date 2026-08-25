# 牛客网 使用指南

## 用途

搜索牛客网（nowcoder.com）的面经数据——面试经验、面试题、面试流程。用于面试准备和了解真实考察内容，不是岗位搜索源。

## 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| keyword | 否 | 搜索关键词，如 `"Agent 开发"`、`"面经"` |
| filter_company | 否 | 按公司筛选，如 `"字节跳动"`、`"腾讯"`，自动拼接到搜索词 |
| is_intern | 否 | `true` 时追加"实习"关键词 |
| order | 否 | 排序：`create`=最新（默认），`quality`=最热 |
| page | 否 | 页码，默认 1 |
| limit | 否 | 返回数量上限，默认 20 |

## 调用示例

```
fetch_company_jobs(company="nowcoder", params='{"keyword":"Agent 开发", "filter_company":"字节跳动", "order":"quality"}')
```

## 返回字段

| 字段 | 说明 |
|------|------|
| title | 面经标题 |
| url | 面经链接（可传给 fetch_jd_detail 获取全文） |
| company | 相关公司 |
| position | 相关岗位 |
| snippet | 内容摘要 |

## 注意事项

1. 这是**面经数据源**：返回的"岗位"实为面经条目
2. 高频面试题分析：抓多条面经 → 用 fetch_jd_detail 读全文 → 汇总问题列表
3. 牛客网关有 WAF，抓取走 Playwright 真实浏览器，速度较慢属正常
