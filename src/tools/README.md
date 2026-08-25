# MCP 工具

Career Kit 提供的 MCP 工具，用于职业规划全流程。

核心理念：**顺序归产品，时间归用户**——不为任务设定时限，日程表由 LLM 在对话中一次性产出（markdown/HTML），系统不存储日程。

## 工具总览（共 21 个）

### 建档工具

| 工具 | 文件 | 作用 |
|------|------|------|
| `start_session` | session.py | 初始化会话 |
| `parse_resume` | resume_parser.py | 解析简历文件 |
| `import_jd` | server.py | 导入 JD 文本 |
| `import_jd_file` | resume_parser.py | 从文件导入 JD |
| `intake` | profile.py | 填充档案（who/have/want，技能需带证据） |
| `finalize_profile` | server.py | 确认档案 |

### 数据获取与分析工具

| 工具 | 文件 | 作用 |
|------|------|------|
| `list_data_sources` | scrapers/loader.py | 列出可用企业数据源及参数 |
| `get_scraper_guide` | server.py（读各包 guide.md） | 读取指定数据源使用教程 |
| `fetch_company_jobs` | scrapers/loader.py | 抓取企业岗位/面经（含薪资） |
| `fetch_jd_detail` | scrapers/loader.py | 获取 JD 全文 |
| `search_knowledge` | knowledge_search.py | 检索本地知识库 |

### 规划工具

| 工具 | 文件 | 作用 |
|------|------|------|
| `analyze_gaps` | methodology.py + gap_analyzer.py | 返回分析方法论上下文 |
| `save_gap_analysis` | gap_analyzer.py | 保存分析结果 |
| `generate_roadmap` | methodology.py + roadmap.py | 返回路线图方法论上下文 |
| `save_roadmap` | roadmap.py | 保存路线图（任务字段 name/description/priority，无时长） |

### 任务执行工具

| 工具 | 文件 | 作用 |
|------|------|------|
| `generate_tasks` | task_manager.py | 从路线图生成任务（重建时沉淀历史进度为能力证据） |
| `get_next_tasks` | task_manager.py | 当前阶段的下一步任务（关卡式） |
| `checkin_task` | task_manager.py | 打卡（完成自动沉淀能力证据） |

### 洞察与产出工具

| 工具 | 文件 | 作用 |
|------|------|------|
| `trigger_insight` | insight.py | 触发洞察（仅 stage_audit / event 两种） |
| `apply_insight` | insight.py | 应用洞察结果（调整类型：add/remove/modify） |
| `get_progress` | task_manager.py | 查看整体进度 |
| `get_workflow_status` | server.py | 工作流状态 + 目标变更检测 |
| `export_dashboard` | server.py | 生成内嵌数据的自包含 HTML 仪表盘 |
| `import_plan` | plan_importer.py | 导入既有规划文档（对比取舍在对话中完成） |

## 工作流

```
建档 → 分析 → 路线图 → 任务执行 → 打卡 → 阶段审计/事件洞察 → 循环
```

详细流程见 [llms.txt](../../llms.txt)
