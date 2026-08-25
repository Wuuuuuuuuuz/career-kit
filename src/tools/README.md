# MCP 工具

Career Kit 提供的 MCP 工具，用于职业规划全流程。

## 工具总览

### 建档工具

| 工具 | 文件 | 作用 |
|------|------|------|
| `start_session` | session.py | 初始化会话 |
| `intake` | profile.py | 填充档案（who/have/want） |
| `finalize_profile` | profile.py | 确认档案 |
| `import_jd` | profile.py | 导入 JD |

### 分析工具

| 工具 | 文件 | 作用 |
|------|------|------|
| `analyze_gaps` | gap_analyzer.py | 差距分析 |
| `save_gap_analysis` | gap_analyzer.py | 保存分析结果 |
| `search_market` | market.py | 搜索市场信息 |

### 规划工具

| 工具 | 文件 | 作用 |
|------|------|------|
| `generate_roadmap` | roadmap.py | 生成路线图 |
| `save_roadmap` | roadmap.py | 保存路线图 |
| `generate_schedule` | schedule.py | 生成日程 |
| `save_schedule` | schedule.py | 保存日程 |

### 任务管理工具

| 工具 | 文件 | 作用 |
|------|------|------|
| `generate_tasks` | task_manager.py | 从路线图生成任务 |
| `get_today_tasks` | task_manager.py | 获取今日任务 |
| `checkin_task` | task_manager.py | 打卡任务 |

### 洞察工具

| 工具 | 文件 | 作用 |
|------|------|------|
| `trigger_insight` | insight.py | 触发洞察分析 |
| `apply_insight` | insight.py | 应用洞察结果 |
| `get_progress` | task_manager.py | 查看进度 |
| `suggest_adjustment` | task_manager.py | 提出调整建议 |

### 状态查询工具

| 工具 | 文件 | 作用 |
|------|------|------|
| `get_workflow_status` | server.py | 获取工作流状态 |

## 工作流

```
建档 → 分析 → 规划 → 任务管理 → 执行 → 洞察调整
```

详细流程见 [llms.txt](../../llms.txt)
