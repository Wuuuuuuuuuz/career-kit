# MCP 工具

> Career Kit 提供的 MCP 工具，用于职业规划全流程（共 24 个）
>
> 核心理念：**顺序归产品，时间归用户**——不为任务设定时限；日程由 LLM 在对话中一次性产出 markdown/HTML 文档，系统不存储。

## 工具总览

### 建档工具

| 工具 | 作用 | 调用时机 |
|------|------|----------|
| `start_session` | 初始化会话 | 用户开始新规划时 |
| `parse_resume` | 解析简历文件 | 用户给了简历时 |
| `import_jd` / `import_jd_file` | 导入目标 JD | 有目标岗位时 |
| `intake` | 填充档案（who/have/want，技能带证据与置信度） | 逐步填充用户信息 |
| `finalize_profile` | 确认档案并生成摘要 | 档案完整后 |

### 数据获取工具

| 工具 | 作用 | 调用时机 |
|------|------|----------|
| `list_data_sources` | 列出可用企业数据源及参数 | 需要真实数据时先调用 |
| `get_scraper_guide` | 读取指定数据源的完整教程 | 第一次使用某源前 |
| `fetch_company_jobs` | 抓取企业岗位/面经（含薪资），自动写入知识库 | 分析和规划前必须调用 |
| `fetch_jd_detail` | 获取 JD 全文 | 深入分析某岗位时 |
| `search_knowledge` | 检索本地知识库（~/.career-kit/knowledge/） | 查找已积累的资料 |

### 分析规划工具

| 工具 | 作用 | 调用时机 |
|------|------|----------|
| `analyze_gaps` | 返回分析方法论上下文 | 真实数据就绪后 |
| `save_gap_analysis` | 保存分析结果 | LLM 分析完成后 |
| `generate_roadmap` | 返回路线图方法论上下文 | 差距分析完成后 |
| `save_roadmap` | 保存路线图（无时长字段，阶段 id 自动规范化） | LLM 生成完成后 |

### 任务执行工具

| 工具 | 作用 | 调用时机 |
|------|------|----------|
| `generate_tasks` | 从路线图生成任务（重建时历史进度沉淀为能力证据） | save_roadmap 之后 |
| `get_next_tasks` | 当前阶段的下一步任务（关卡式） | 用户想知道「现在做什么」 |
| `checkin_task` | 打卡（完成自动沉淀能力证据） | 用户完成/跳过任务时 |

### 洞察与产出工具

| 工具 | 作用 | 调用时机 |
|------|------|----------|
| `trigger_insight` | 触发洞察分析（仅 stage_audit / event） | 阶段完成或用户报告事件 |
| `apply_insight` | 应用洞察结果（add/remove/modify 任务） | LLM 分析完成后 |
| `get_progress` | 查看整体进度 | 用户想了解进度时 |
| `get_workflow_status` | 工作流状态 + 目标变更检测 | 不确定下一步时 |
| `export_dashboard` | 生成自包含 HTML：`mode="progress"` 进度仪表盘（默认）/ `mode="roadmap"` 职业地图（完整路线图+执行进度+JD 依据/占位徽标） | 用户想直观查看进度或可携带路线图时 |
| `import_plan` | 导入既有规划文档（对比取舍在对话中完成） | 用户有旧计划要迁移时 |

## 工作流

```
建档 → 分析 → 规划 → 任务执行 → 打卡 → 阶段审计/事件洞察 → 循环
```

详细流程见 [工作流详解](workflow.md)

## 工具详情

每个工具的详细文档在源码文件的 docstring 中：

| 分类 | 文件 | 文档 |
|------|------|------|
| 建档 | `src/tools/profile.py`, `src/tools/session.py`, `src/server.py` | 档案管理工具 |
| 数据获取 | `src/scrapers/loader.py`, `src/tools/knowledge_search.py` | 抓取与检索工具 |
| 分析规划 | `src/tools/gap_analyzer.py`, `src/tools/roadmap.py` | 分析与路线图工具 |
| 任务执行 | `src/tools/task_manager.py` | 任务管理工具 |
| 洞察 | `src/tools/insight.py` | 洞察引擎工具 |
