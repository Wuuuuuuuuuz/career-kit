# 字节跳动

> 字节跳动岗位数据源

## 搜索岗位

```
fetch_company_jobs(company="bytedance", params='{"keyword":"Python", "city":"上海"}')
```

## 参数

| 参数 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `keyword` | 是 | 搜索关键词 | `"Python"`, `"AI Agent"` |
| `city` | 否 | 城市名 | `"上海"`, `"北京"` |
| `job_type` | 否 | 岗位类型 | `"社招"`, `"校招"` |
| `limit` | 否 | 返回数量 | `10`, `20` |

## 获取详情

```
fetch_jd_detail(url="https://jobs.bytedance.com/...")
```

### 返回字段

| 字段 | 说明 |
|------|------|
| `title` | 岗位名称 |
| `company` | 公司名称 |
| `location` | 工作地点 |
| `salary` | 薪资范围 |
| `description` | 岗位描述（JD 全文） |
| `requirements` | 任职要求 |

## 特点

- 支持社招和校招
- 数据更新频率高
- 无需登录
