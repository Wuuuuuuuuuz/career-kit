# BOSS直聘

> BOSS直聘岗位数据源

## 搜索岗位

```
fetch_company_jobs(company="boss", params='{"keyword":"Python", "city":"上海"}')
```

## 参数

| 参数 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `keyword` | 是 | 搜索关键词 | `"Python"`, `"AI Agent"` |
| `city` | 否 | 城市名或代码 | `"上海"`, `"101020100"` |
| `experience` | 否 | 经验要求 | `"1-3年"`, `"3-5年"` |
| `degree` | 否 | 学历要求 | `"本科"`, `"硕士"` |
| `salary` | 否 | 薪资范围 | `"15-25K"` |
| `limit` | 否 | 返回数量 | `10`, `20` |

## 城市代码

| 城市 | 代码 |
|------|------|
| 全国 | 100010000 |
| 北京 | 101010100 |
| 上海 | 101020100 |
| 深圳 | 101280600 |
| 广州 | 101280100 |
| 杭州 | 101210100 |

完整城市码表：[city_codes.json](../../src/scrapers/boss/city_codes.json)

## 获取详情

```
fetch_jd_detail(url="https://www.zhipin.com/job_detail/xxx.html")
```

### 返回字段

| 字段 | 说明 |
|------|------|
| `title` | 岗位名称 |
| `company` | 公司名称 |
| `location` | 工作地点 |
| `salary` | 薪资范围 |
| `description` | 岗位描述（JD 全文） |

## 首次使用

1. 安装依赖：`pip install iv8`
2. 登录：运行 `python -m src.scrapers.boss.login`
3. 在浏览器中完成登录
4. 后续自动复用 cookies

## 错误处理

| 错误 | 原因 | 解决 |
|------|------|------|
| `需要登录` | cookies 不存在或过期 | 重新登录 |
| `code=36` | 账户风控 | 等待 30 分钟 |
| `code=37` | 需要 stoken | 自动计算（需安装 iv8） |
| `stoken 计算失败` | iv8 未安装 | `pip install iv8` |
