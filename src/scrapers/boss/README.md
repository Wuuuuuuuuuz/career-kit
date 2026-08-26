# BOSS 直聘 Scraper

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

完整城市码表：[city_codes.json](city_codes.json)

## 获取详情

```
fetch_jd_detail(url="https://www.zhipin.com/job_detail/xxx.html")
```

返回字段：
- `title` - 岗位名称
- `company` - 公司名称
- `location` - 工作地点
- `salary` - 薪资范围
- `description` - 岗位描述（JD 全文）

## 首次使用

1. 安装依赖：`pip install -e .`（含 iv8 与 websockets）
2. 登录：在本项目目录运行 `python -m src.scrapers.boss.login`
   —— 会拉起一个独立 Chrome 窗口，在其中完成扫码登录后回车即可；
   cookies 落盘后长期复用（过期重跑一次）
3. 后续 `search` / `get_detail` 自动携带登录态

## 错误处理

| 错误 | 原因 | 解决 |
|------|------|------|
| `需要登录` | cookies 不存在或过期 | 重新运行上面的登录命令 |
| `code=36` | 账户风控 | 等待 30 分钟 |
| `code=37` | 需要 stoken | 自动计算 |
| `stoken 计算失败` | 网络或 JS 拉取失败 | 重试；持续失败检查网络 |

> 注：`salary` 参数为近似过滤，日薪岗可能混入结果（BOSS API 行为）。