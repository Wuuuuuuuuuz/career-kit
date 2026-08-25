# MCP 工具

> Career Kit 提供的 MCP 工具，用于职业规划全流程

## 工具总览

### 建档工具

| 工具 | 作用 | 调用时机 |
|------|------|----------|
| `start_session` | 初始化会话 | 用户开始新规划时 |
| `intake` | 填充档案（who/have/want） | 逐步填充用户信息 |
| `finalize_profile` | 确认档案 | 档案完整后 |
| `import_jd` | 导入 JD | 有目标岗位时 |

### 分析工具

| 工具 | 作用 | 调用时机 |
|------|------|----------|
| `analyze_gaps` | 差距分析 | 档案确认后 |
| `save_gap_analysis` | 保存分析结果 | LLM 分析完成后 |
| `search_market` | 搜索市场信息 | 需要补充数据时 |

### 规划工具

| 工具 | 作用 | 调用时机 |
|------|------|----------|
| `generate_roadmap` | 生成路线图 | 差距分析完成后 |
| `save_roadmap` | 保存路线图 | LLM 生成完成后 |
| `generate_schedule` | 生成日程 | 路线图保存后 |
| `save_schedule` | 保存日程 | LLM 生成完成后 |

### 任务管理工具

| 工具 | 作用 | 调用时机 |
|------|------|----------|
| `generate_tasks` | 从路线图生成任务 | 路线图和日程保存后 |
| `get_today_tasks` | 获取今日任务 | 用户想查看任务时 |
| `checkin_task` | 打卡任务 | 用户完成任务时 |

### 洞察工具

| 工具 | 作用 | 调用时机 |
|------|------|----------|
| `trigger_insight` | 触发洞察分析 | 阶段完成/事件/定期 |
| `apply_insight` | 应用洞察结果 | LLM 分析完成后 |
| `get_progress` | 查看进度 | 用户想了解进度时 |
| `suggest_adjustment` | 提出调整建议 | 有超期任务时 |

### 状态查询工具

| 工具 | 作用 | 调用时机 |
|------|------|----------|
| `get_workflow_status` | 获取工作流状态 | 不确定下一步时 |

## 工作流

```
建档 → 分析 → 规划 → 任务管理 → 执行 → 洞察调整
```

详细流程见 [工作流详解](workflow.md)

## 工具详情

每个工具的详细文档在源码文件的 docstring 中：

| 分类 | 文件 | 文档 |
|------|------|------|
| 建档 | `src/tools/profile.py` | 档案管理工具 |
| 分析 | `src/tools/gap_analyzer.py` | 差距分析工具 |
| 规划 | `src/tools/roadmap.py` | 路线图工具 |
| 规划 | `src/tools/schedule.py` | 日程工具 |
| 任务 | `src/tools/task_manager.py` | 任务管理工具 |
| 洞察 | `src/tools/insight.py` | 洞察引擎工具 |
