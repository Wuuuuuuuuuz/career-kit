# Career Kit 实现路径

> Phase 分解、技术选型、风险应对

---

## 1. 实现路径总览

| Phase | 目标 | 状态 | 负责 |
|-------|------|------|------|
| Phase 1 | 框架基础设施 | ✅ 已完成 | 核心团队 |
| Phase 2 | 职业教练系统 | ⬅️ 当前 | 核心团队 |
| Phase 3 | 社区贡献启动 | 待开始 | 社区 |
| Phase 4 | 检索升级 | 待开始 | 核心团队 |
| Phase 5 | 分析优化 | 待开始 | 核心团队 |
| Phase 6 | 生态扩展 | 持续 | 社区 |

---

## 2. Phase 1: 框架基础设施 ✅ 已完成

**目标**：让社区贡献 scraper 变得简单

### 完成内容

- [x] `CompanyScraper` 基类接口
- [x] `config.yaml` 注册机制
- [x] `loader.py` 动态加载
- [x] `knowledge_writer.py` 数据自动积累
- [x] `_template/` 贡献模板
- [x] `CONTRIBUTING.md` 贡献指南
- [x] 字节跳动 scraper 集成知识写入

### 验收标准

字节 scraper 抓取后，`dev/knowledge/jds/bytedance/` 自动出现新文件

---

## 3. Phase 2: 职业教练系统 ⬅️ 当前

**目标**：从信息查询工具升级为有真实数据的 AI 职业陪练

### 核心 Loop

```
用户目标 → AI 分析差距 → 设计路线图 → 细化到每天任务 → 用户打卡 → AI 洞察调整 → 达成目标
```

### 子阶段

#### Phase 2.1: 数据模型扩展

- [ ] 新增 `Task` 模型（id, name, deadline, status, priority）
- [ ] 新增 `CheckIn` 模型（task_id, timestamp, status, notes）
- [ ] 新增 `Adjustment` 模型（trigger, trigger_type, changes）
- [ ] 更新 `CareerProfile`，添加 checkins 和 adjustments 字段

#### Phase 2.2: 任务管理 + 洞察引擎

- [ ] `task_manager.py`：任务创建、打卡、调整
- [ ] `insight.py`：洞察检查、调整建议
- [ ] 实现三种触发方式（阶段审计、事件触发、主动检查）

#### Phase 2.3: 静态前端

- [ ] `dashboard.html`：进度仪表盘
- [ ] 读取 `progress.json` 显示进度
- [ ] 支持任务勾选打卡

#### Phase 2.4: MCP Tools 集成

- [ ] `get_today_tasks`：获取今日任务
- [ ] `checkin_task`：打卡任务
- [ ] `get_progress`：获取进度
- [ ] `trigger_insight`：触发洞察
- [ ] `suggest_adjustment`：提出调整建议
- [ ] `apply_adjustment`：应用调整

#### Phase 2.5: 测试 & 打磨

- [ ] 端到端测试
- [ ] Prompt 优化
- [ ] 用户体验优化

### 验收标准

1. 用户可以查看今日任务并打卡
2. AI 在阶段完成后自动触发审计
3. AI 在用户报告事件时主动提出调整
4. 超期任务自动压缩后续时长

---

## 4. Phase 3: 社区贡献启动

**目标**：吸引社区贡献 3-5 个主流企业 scraper

### 待完成内容

- [ ] 发布贡献指南
- [ ] 提供 Boss 直聘 scraper 示例（Playwright 模式）
- [ ] 提供牛客面经 scraper 示例（httpx API 模式）
- [ ] 合并社区 PR

### 目标企业

| 企业 | 数据类型 | 实现难度 | 参考 |
|------|----------|----------|------|
| Boss 直聘 | JD | 中 | eatmoreduck/boss-zhipin-scraper |
| 牛客 | 面经 | 低 | httpx 直调 API |
| 小红书 | 面经 | 高 | MediaCrawler |
| 拉勾 | JD | 低 | httpx + API |
| 美团 | JD | 中 | Playwright XHR |
| 腾讯 | JD | 中 | Playwright XHR |
| 阿里 | JD | 中 | Playwright XHR |
| 华为 | JD | 低 | httpx + API |
| 知乎 | 职业讨论 | 高 | 需登录态 |

### 验收标准

社区贡献 3+ 个企业 scraper，数据自动写入知识库

---

## 5. Phase 4: 检索升级

**目标**：从关键词匹配升级到语义搜索

### 方案选择

| 方案 | 优势 | 劣势 |
|------|------|------|
| TF-IDF | 零依赖，轻量 | 无语义理解 |
| BM25 | 经典检索算法，效果好 | 仍无语义 |
| **sentence-transformers** | 本地语义搜索，隐私友好 | 需要下载模型 (~100MB) |
| OpenAI Embedding | 效果最好 | 需要 API key，数据外传 |

**推荐方案：sentence-transformers 本地模型**

理由：
- 本地运行，数据不离开用户电脑
- 模型一次下载，离线可用
- 中文支持好

### 推荐模型

| 场景 | 推荐模型 | 维度 | 说明 |
|------|----------|------|------|
| 中文首选 | `BAAI/bge-base-zh-v1.5` | 768 | MTEB 中文榜前列 |
| 轻量/速度优先 | `shibing624/text2vec-base-chinese` | 768 | ~100M 参数 |
| 多语言兜底 | `paraphrase-multilingual-MiniLM-L12-v2` | 384 | 50+ 语言 |
| 长文档 | `BAAI/bge-m3` | - | 支持 8192 上下文 |

**向量存储方案**：小规模（<50 万条）用 numpy + 余弦相似度即可

### 待完成内容

- [ ] 集成 `sentence-transformers`（`BAAI/bge-base-zh-v1.5`）
- [ ] 实现 `SemanticRetriever` 类
- [ ] 实现文档索引和增量更新
- [ ] 替换 `DataRouter` 的检索逻辑

### 验收标准

搜索"双非转AI"能找到"非985背景转型人工智能"的案例

---

## 6. Phase 5: 分析优化

**目标**：提高分析结果的稳定性和可用性

### 当前问题

1. **Prompt 模板变量替换脆弱**：`.format()` 替换，缺失变量会报错
2. **输出格式解析不稳定**：正则从 markdown code block 提取 JSON
3. **SOP 步骤间上下文传递不完整**：检索结果只取前 500 字符

### 待完成内容

- [ ] 优化 prompt 结构，减少 token 消耗
- [ ] 增加 JSON 输出的容错解析
- [ ] 实现分析结果的结构化校验
- [ ] 添加 MCP Resources 暴露知识库数据

### 短期优化：结构化 prompt

当前 prompt 太长，LLM 容易"跑偏"。优化为：

```python
def build_analysis_prompt(profile, search_results):
    return f"""分析以下求职者档案，输出 JSON。

## 档案
{json.dumps(profile, ensure_ascii=False)}

## 参考数据
{format_search_results(search_results)}

## 输出格式（严格遵守）
```json
{{
  "match_score": <0-100>,
  "skill_gaps": [...],
  "priority_actions": [...]
}}
```

只输出 JSON，不要其他内容。"""
```

### 验收标准

`analyze_gaps` 返回的 JSON 能稳定解析

---

## 7. Phase 6: 生态扩展

**目标**：持续扩展功能和社区

### 待完成内容

- [ ] 面经 scraper 模板（牛客/小红书）
- [ ] 定时批量抓取调度
- [ ] 数据去重与更新机制
- [ ] 社区贡献排行榜
- [ ] Web UI 可视化

---

## 8. 技术选型总结

| 组件 | 选型 | 理由 |
|------|------|------|
| MCP 框架 | FastMCP | 已有，成熟 |
| 数据校验 | Pydantic | 已有，类型安全 |
| HTTP 客户端 | httpx | 已有，异步支持 |
| 浏览器自动化 | Playwright | 已有，处理 SPA |
| 语义搜索 | sentence-transformers | 本地运行，中文支持好 |
| 向量存储 | numpy + 文件 | 简单，无外部依赖 |
| 配置格式 | YAML | 已有，人类可读 |
| 数据存储 | JSON + Markdown | 结构化 + 可读性，隐私友好 |
| 知识写入 | knowledge_writer.py | 框架自动调用，贡献者无感 |
| 反馈持久化 | feedback_writer.py | 半自动，用户可控 |

**关键设计决策**：
- JD 用 JSON 格式（结构化，便于检索）
- 面经用 Markdown 格式（可读性好，便于 LLM 理解）
- 反馈用 Markdown + frontmatter（可读 + 结构化元数据）
- 缓存用文件系统（简单，无外部依赖）

---

## 9. 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 反爬升级 | scraper 失效 | 多源备份，定期维护 |
| 模型下载大 | 首次使用慢 | 提供离线包，按需下载 |
| 知识库膨胀 | 检索变慢 | 定期清理过期数据，限制大小 |
| LLM 输出不稳定 | 解析失败 | 容错解析 + 重试机制 |
| 反馈噪声 | 无效反馈影响分析 | 分类过滤，权重衰减 |
| 用户隐私 | 反馈可能含敏感信息 | 本地存储，不上传 |

---

*最后更新：2026-08-21*
