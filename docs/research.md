# Career Kit 调研文档

> 竞品分析、模式总结、设计启示

---

## 1. 调研目的

了解同类项目的做法，为 career-kit 的差距分析和路线图设计提供参考。

---

## 2. MCP 服务器类

| 项目 | Stars | 做了什么 | 缺什么 | 值得学的 |
|------|-------|---------|--------|---------|
| [Workopia MCP](https://github.com/workopia/workopia-mcp) | 270 | 岗位搜索、简历定制、求职信 | 无档案、无路线图 | 干净的 MCP tool 设计（5 个聚焦工具） |
| [Career Agents](https://github.com/karthikrshet/Career-Agents) | 36 | 全链路，167 个 agent | 太重，19 个部门 | 80-85% token 优化引擎、模块化 agent 架构 |
| [JobGPT MCP](https://github.com/6figr-com/jobgpt-mcp-server) | 20 | 岗位搜索、自动投递、简历 | 无差距分析、无路线图 | 多客户端支持模式 |
| [Career Compass MCP](https://github.com/benskamps/career-compass-mcp) | 4 | 本地优先 MCP + Career KB | 无差距分析、无路线生成 | 本地隐私架构（`~/.career-compass/`）、YAML 数据模型 |
| [SkillMatch MCP](https://github.com/jarmstrong158/skillmatch-mcp) | 2 | 简历 vs 岗位匹配 | 无路线图、无日程 | GitHub 作品集分析作为技能证据 |
| [CareerLens MCP](https://github.com/upretisaurav/careerlens-mcp) | 1 | 薪资基准、技能需求分析 | 无路线图、无日程 | 薪资基准数据 |
| [Go-Job MCP](https://github.com/anatolykoptev/go-job) | 4 | 岗位搜索 | 仅此而已 | — |

---

## 3. AI 求职 Agent 类

| 项目 | Stars | 做了什么 | 缺什么 | 值得学的 |
|------|-------|---------|--------|---------|
| [Job Search Agent](https://github.com/surapuramakhil-org/Job_search_agent) | 172 | 自动搜索和投递 | 无档案、无路线图 | 自动化投递模式 |
| [Agentic Career Search](https://github.com/Francis1998/agentic-career-search) | 101 | 40+ ATS 平台适配 | 无路线图、无日程 | 确定性决策引擎 + LLM 降级策略、持久化事件日志 |
| [JobPilot](https://github.com/suxrobGM/jobpilot) | 54 | 浏览器自动投递 | 无差距分析、无路线图 | Playwright 浏览器自动化 |
| [Job Hunter Team](https://github.com/leopu00/job-hunter-team) | 43 | 多 agent 团队求职 | 无路线图 | 多 agent 团队分工模式 |
| [TechGenie](https://github.com/hl-yang96/TechGenie) | 54 | 技术职业辅导 + 代码分析 | 无路线图、无日程 | 代码分析作为技术能力证据 |
| [InterviewAce AI](https://github.com/rohith-chitturi/InterviewAce-AI) | 10 | AI 模拟面试 + 知识差距检测 | 无路线图 | 语音交互面试准备 |
| [Non-Tech Job Navigator](https://github.com/dungnotnull/nontech-job-navigator-agent) | 3 | 完整链路：建档→分析→路线图 | 场景窄（越南蓝领） | 状态机引导、三路径模型、周级路线图、情绪支持层 |

---

## 4. 路线图生成类

| 项目 | Stars | 做了什么 | 值得学的 |
|------|-------|---------|---------|
| [GetRoadMaps](https://github.com/habeebmoosa/getroadmaps) | 4 | AI 路线图生成 | 多 AI 提供商支持 |
| [Career Craft AI](https://github.com/Yagna123k/CAREER-CRAFT-AI) | 12 | 全家桶：顾问+路线图+作品集+面试 | 四合一产品架构 |
| [roadmap.sh](https://github.com/kamranahmedse/developer-roadmap) | 310K+ | 社区驱动的开发者路线图 | 交互式路线图可视化 UX 标准 |

---

## 5. MCP 规划/效率类

| 项目 | Stars | 做了什么 | 值得学的 |
|------|-------|---------|---------|
| [Shiori-v1](https://github.com/kaorii-ako/Shiori-v1) | 43 | AI 学习伴侣 + MCP | 学习计划模型（profile→plan→track→adapt） |
| [Aeman](https://github.com/aenix-io/aeman) | 26 | 团队短期规划 + MCP | 单二进制部署、基于 GitHub Projects v2 |
| [Wingman MCP](https://github.com/adeoluwaadesina/wingman-mcp) | 4 | Claude 对话中的待办面板 | SQLite 本地持久化 |
| [Plan Tracker MCP](https://github.com/hinayoung23/plan-tracker) | 1 | 长期计划追踪 + 里程碑 | 里程碑 + 每日签到模式 |
| [Syllabus-to-Study-Plan MCP](https://github.com/Kangaeruhito14/Syllabus-to-Study-Plan-MCP-Server) | 0 | 课表→日程→日历导出 | ICS 日历导出、多客户端支持 |

---

## 6. Claude Code Skill 类

| 项目 | Stars | 做了什么 | 值得学的 |
|------|-------|---------|---------|
| [Career Agent Skills](https://github.com/art2url/career-agent-skills) | 8 | 简历/面试/求职信等 skill 集合 | skill.md 格式跨平台分发 |
| [AI Career Planner Skill](https://github.com/ayush488-glitch/ai-career-planner-skill) | 191 | 6 个月拿到 AI 岗位计划 | 聚焦的产品形态（"6个月计划"），说明需求很大 |

---

## 7. ATS 简历匹配工具

### Resume-ATS-Tracking-LLM-Project (39 stars)
- 链接：https://github.com/Deba951/Resume-ATS-Tracking-LLM-Project
- 做法：Streamlit + Gemini，输入 JD + 简历 PDF → 匹配百分比 + 缺失关键词 + 改进建议
- 启发：简单的 prompt 模式，LLM 扮演 ATS 角色评估简历

### JobMatchAI (22 stars)
- 链接：https://github.com/wadekarg/JobMatchAI
- 做法：Chrome 扩展，浏览 JD 时一键分析
- 输出：Match Score + 匹配技能 + 缺失技能 + ATS 关键词 + 简历改写建议 + Cover Letter 生成
- 启发：skill gap analysis 的结构化输出（matching skills / missing skills / insights / recommendations）

### ResumeIQ (9 stars)
- 链接：https://github.com/rohith-chitturi/ResumeIQ
- 做法：Pipeline 引擎架构（Parse → Embedding → Constraint → Retrieve → LLM → Validation）
- 核心洞察：**确定性差距分析在 LLM 之前做**，LLM 只做呈现层。避免 LLM 幻觉，给出精确匹配分数
- 启发：混合检索（精确关键词 + 语义搜索）比纯 LLM 更可靠

### ai-resume-analyzer (16 stars)
- 链接：https://github.com/dutta-sujoy/ai-resume-analyzer
- 做法：虚拟 HR 角色，分析优势/劣势 + 推荐课程 + JD 匹配分数
- 启发：除了匹配度，还推荐学习课程来弥补差距

---

## 8. 共性模式总结

### 8.1 ATS/简历工具共性

几乎每个 ATS/简历工具都包含：
1. **Match Score (0-100)** — 快速判断匹配度
2. **Matching Skills** — 用户已有的技能
3. **Missing Skills** — 缺失的技能
4. **ATS Keywords** — 简历必须出现的关键词
5. **Recommendations** — 具体改进建议

### 8.2 求职 Agent 共性

1. **自动化投递** — 浏览器自动化填写表单
2. **多平台适配** — 40+ ATS 平台支持
3. **状态追踪** — 持久化事件日志
4. **降级策略** — LLM 不可用时的确定性决策

### 8.3 MCP Server 共性

1. **工具聚焦** — 每个 tool 做一件事
2. **本地优先** — 数据存储在用户电脑
3. **配置驱动** — YAML/JSON 定义行为
4. **多客户端支持** — Claude/Cursor/Windsurf 都能用

---

## 9. 市场空白

没有一个项目把「建档 → 差距分析 → 路线图 → 日程 → 持续追踪」串成完整闭环。最接近的几个：

1. **Career Agents**（36 stars）——全链路但太重（167 个 agent）
2. **Non-Tech Job Navigator**（3 stars）——架构最好但场景窄
3. **Career Compass MCP**（4 stars）——本地优先设计好但缺分析和路线

191 star 的 AI Career Planner Skill 说明需求很大，但它只是一次性输出计划，没有持续追踪。

---

## 10. 对 career-kit 的启示

### 10.1 差异化

市面上的工具都是「输入 JD → 输出匹配度」的**一次性**模式。career-kit 做的是**持续闭环**：
建档 → 差距分析 → 路线图 → 日程 → 追踪 → 循环

### 10.2 采用的模式

| 模式 | 来源 | 用在 career-kit |
|------|------|----------------|
| 方法论驱动（YAML 指引 + LLM 自主执行） | ResumeIQ Pipeline 思想 | methodology.py 差距分析 |
| 状态机引导 | Non-Tech Job Navigator | intake 阶段 |
| 本地优先 + JSON | Career Compass | 数据存储 |
| 任务级打卡 + 洞察调整 | Plan Tracker MCP | checkin_task / trigger_insight |
| ICS 日历导出 | Syllabus-to-Study-Plan MCP | generate_schedule |

### 10.3 四阶段路线图模型

参考 roadmap.sh (310K+ stars) 的交互式路线图思路，结合用户需求设计了 learn/project/intern/research 四阶段分类。

---

## 11. 调研参考链接

### 企业库框架参考

| 项目 | 参考价值 |
|------|----------|
| [scrapy/scrapy](https://github.com/scrapy/scrapy) | 爬虫框架设计、中间件、管道 |
| [apify/apify-sdk-python](https://github.com/apify/apify-sdk-python) | Actor 模式、数据存储、社区贡献 |
| [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) | 多平台 scraper 组织方式 |

### Scraper 实现参考

| 项目 | Stars | 参考价值 |
|------|-------|----------|
| [eatmoreduck/boss-zhipin-scraper](https://github.com/eatmoreduck/boss-zhipin-scraper) | 1180 | Boss 直聘 CDP 方案、反检测 |
| [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) | 15K+ | 小红书/抖音 Playwright XHR 拦截 |
| [ReaJason/xhs](https://github.com/ReaJason/xhs) | 1K+ | 小红书 API 封装 |

### 语义检索参考

| 项目 | 参考价值 |
|------|----------|
| [BAAI/bge-base-zh-v1.5](https://huggingface.co/BAAI/bge-base-zh-v1.5) | 中文语义搜索首选模型 |
| [shibing624/text2vec](https://github.com/shibing624/text2vec) | 轻量中文 embedding 方案 |
| [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) | 多语言长文档检索 |

### 反馈循环参考

| 项目 | 参考价值 |
|------|----------|
| [LangChain memory](https://github.com/langchain-ai/langchain) | 对话记忆、持久化 |
| [Mem0](https://github.com/mem0ai/mem0) | 用户记忆管理、自动提取 |
| [Plan Tracker MCP](https://github.com/hinayoung23/plan-tracker) | 进度签到、偏差分析 |

### MCP 生态参考

| 项目 | Stars | 参考价值 |
|------|-------|----------|
| [Workopia MCP](https://github.com/workopia/workopia-mcp) | 270 | 干净的 MCP tool 设计 |
| [Career Compass MCP](https://github.com/benskamps/career-compass-mcp) | 4 | 本地优先架构、YAML 数据模型 |
| [Plan Tracker MCP](https://github.com/hinayoung23/plan-tracker) | 1 | 里程碑 + 每日签到模式 |
| [PrefectHQ/fastmcp](https://github.com/PrefectHQ/fastmcp) | 27k+ | llms.txt 设计，专为 LLM 消费的文档 |
| [googleapis/mcp-toolbox](https://github.com/googleapis/genai-toolbox) | 16k+ | System Directives、Glossary、Diataxis 框架 |

---

## 12. 牛客网面经爬虫调研

### 12.1 参考项目分析

| 项目 | Stars | 技术方案 | 牛客 API | 参考价值 |
|------|-------|----------|----------|----------|
| [NewCoderAgent](https://github.com/bbirdxr/NewCoderAgent) | - | requests + SQLite + DeepSeek LLM | 推测用搜索/Feed API（子模块源码不可访问） | LLM 过滤面经+提取元数据的 pipeline |
| [OfferClaw](https://github.com/InuyashaYang/offerclaw) | - | requests + BeautifulSoup + ChromaDB | 不直接调牛客 API，通过搜狗搜索发现 URL | CSS 选择器提取内容、去重策略 |
| [Crawl4NK](https://github.com/z0l0y/Crawl4NK) | - | requests + BeautifulSoup + jieba | **三个 API 端点**（最有参考价值） | API 端点、反爬处理、内容过滤 |

### 12.2 Crawl4NK 的 API 端点（核心参考）

**搜索 API（POST）**：
- URL: `https://gw-c.nowcoder.com/api/sparta/pc/search`
- Payload: `{"type":"all", "query":"<keyword>", "page":<N>, "tag":[], "order":"create"}`
- 返回分页结果，`records[].data.momentData` 和 `records[].data.contentData`

**详情 API（GET）**：
- URL: `https://gw-c.nowcoder.com/api/sparta/detail/{api_type}/detail/{detail_id}`
- `api_type` 为 `moment-data` 或 `content-data`
- 备选：抓 HTML 页面解析 `window.__INITIAL_STATE__` 嵌入的 JSON

**评论 API（POST）**：
- URL: `https://gw-c.nowcoder.com/api/sparta/reply/v2/reply/list`
- Payload: `{"entityId":<post_id>, "entityType":8, "page":1, "pageSize":50, "order":1}`

### 12.3 OfferClaw 的 CSS 选择器（备选方案）

当 API 不可用时，可回退到 HTML 解析：
- 内容：`div.post-content`, `article`, `div.nc-richtext`, `div.article-content`, `div#thread-post`
- 点赞数：正则匹配 `"likeCount"\s*:\s*(\d+)` 等 JSON 片段
- 发布时间：`"publishTime"` 或 `"createTime"` JSON 字段

### 12.4 反爬策略参考

| 策略 | 来源 | 说明 |
|------|------|------|
| Cookie 配置 | Crawl4NK | 需要浏览器 Cookie，配置文件提供 |
| 请求头伪装 | 全部 | Chrome UA + Origin/Referer |
| 请求间隔 | Crawl4NK / OfferClaw | 0.25-1.5s 随机延迟 |
| 代理轮换 | Crawl4NK | 可选配置代理池 |
| 重试退避 | Crawl4NK | 429/5xx 时指数退避 |
| 内容过滤 | Crawl4NK | AC 自动机黑名单 + 质量评分 |

### 12.5 设计决策

**最终方案：Playwright DOM 抓取搜索结果 + 详情页（已实现）**

> 修正：早期调研结论为"httpx 直调 gw-c.nowcoder.com API"，
> 实现时发现牛客网 gw-c 网关有阿里云 WAF，纯 httpx 指纹无法通过，
> 故改为 Playwright 打开搜索页提取 DOM（subType=818 面经筛选参数）。
> 详情页 `.nc-slate-editor-content` 为 SSR 渲染，无需登录即可提取。

理由：
1. WAF 要求真实浏览器指纹，Playwright 可直接通过
2. 详情页 SSR 渲染，DOM 提取稳定
3. 数据类型：面经（interviews），写入 `data/knowledge/interviews/nowcoder/`

---

*最后更新：2026-08-25*
