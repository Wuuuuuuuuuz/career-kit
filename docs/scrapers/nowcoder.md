# 牛客网

> 牛客网面经数据源

## 搜索面经

```
fetch_company_jobs(company="nowcoder", params='{"keyword":"字节跳动", "type":"面经"}')
```

## 参数

| 参数 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `keyword` | 是 | 搜索关键词 | `"字节跳动"`, `"AI Agent"` |
| `type` | 否 | 内容类型 | `"面经"`, `"笔试"` |
| `company` | 否 | 公司名 | `"字节跳动"`, `"阿里巴巴"` |
| `limit` | 否 | 返回数量 | `10`, `20` |

## 获取详情

```
fetch_jd_detail(url="https://www.nowcoder.com/...")
```

### 返回字段

| 字段 | 说明 |
|------|------|
| `title` | 面经标题 |
| `company` | 公司名称 |
| `position` | 岗位名称 |
| `content` | 面经内容 |
| `interview_round` | 面试轮次 |
| `interview_date` | 面试日期 |

## 特点

- 面经分享平台
- 包含面试题和面试经验
- 支持按公司、岗位筛选
- 无需登录
