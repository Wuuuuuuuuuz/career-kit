# 工作流详解

> Career Kit 完整工作流、前置条件、输入输出

## 工作流总览

```
建档 → 分析 → 规划 → 任务管理 → 执行 → 洞察调整
```

## 阶段 1：建档

### 目标

建立用户职业档案，了解用户是谁、有什么、想要什么。

### 工具

| 工具 | 作用 |
|------|------|
| `start_session` | 初始化会话 |
| `intake` | 填充档案（who/have/want） |
| `finalize_profile` | 确认档案 |
| `import_jd` | 导入 JD（可选） |

### 流程

```
1. start_session()
2. intake(section="who", data='{"name":"张三", "education":"计算机本科"}')
3. intake(section="have", data='{"skills":["Python", "React"], "experience":"1年前端"}')
4. intake(section="want", data='{"target_role":"AI Agent 工程师", "salary":"20k-30k"}')
5. finalize_profile()
```

### 前置条件

- 无

### 输出

- `profile.summary`：档案摘要
- `profile.version`：档案版本

---

## 阶段 2：分析

### 目标

对比用户现状与目标，找出差距，生成差距分析报告。

### 工具

| 工具 | 作用 |
|------|------|
| `list_company_jobs` | 查看可用企业数据源 |
| `fetch_company_jobs` | 抓取真实岗位（含薪资范围） |
| `fetch_jd_detail` | 获取 JD 全文 |
| `search_knowledge` | 检索本地知识库 |
| `analyze_gaps` | 获取分析方法论 |
| `save_gap_analysis` | 保存分析结果 |

### 流程

```
1. list_company_jobs()                              // 查看可用企业
2. fetch_company_jobs(company="bytedance", params='{"keyword":"AI Agent"}')  // 必须调用
3. fetch_jd_detail(url="...")                       // 获取 JD 全文
4. search_knowledge(query="AI Agent 面经")          // 补充本地资料
5. analyze_gaps()
6. save_gap_analysis(gap_json='{"match_score":65, "skill_gaps":[...]}')
```

### 前置条件

- `profile.summary` 已生成（finalize_profile 已调用）

### 输出

- `profile.gap`：差距分析结果
  - `match_score`：匹配度评分（0-100）
  - `skill_gaps`：技能差距列表
  - `priority_actions`：优先行动项

### 关键规则

1. **必须先抓取真实数据**：在调用 `save_gap_analysis` 之前，必须用 `fetch_company_jobs` / `fetch_jd_detail` / `search_knowledge` 获取真实数据
2. **标注数据来源**：gap_json 中的每个差距应标注数据来源（如 `"source": "BOSS直聘 JD"`）
3. **不要凭空分析**：差距必须基于真实市场数据，不能凭 LLM 自身知识；薪资行情从岗位搜索结果的 salary 字段汇总

---

## 阶段 3：规划

### 目标

基于差距分析，生成分阶段路线图和日程表。

### 工具

| 工具 | 作用 |
|------|------|
| `generate_roadmap` | 获取路线图方法论 |
| `save_roadmap` | 保存路线图 |
| `generate_schedule` | 获取日程方法论 |
| `save_schedule` | 保存日程 |

### 流程

```
1. generate_roadmap()
2. save_roadmap(roadmap_json='{"phases":[...]}')
3. generate_schedule(scope="this_week")
4. save_schedule(schedule_json='{"schedule":[...]}')
```

### 前置条件

- `profile.gap` 已生成（save_gap_analysis 已调用）

### 输出

- `profile.plan.roadmap`：路线图
  - `phases`：阶段列表
  - 每个阶段包含 `name`、`milestones`、`tasks`
- `profile.plan.schedule`：日程表

### 关键规则

1. **基于真实数据规划**：路线图中的任务应基于市场真实要求
2. **标注数据来源**：路线图中的任务应标注数据来源

---

## 阶段 4：任务管理

### 目标

将路线图转化为可执行的任务列表。

### 工具

| 工具 | 作用 |
|------|------|
| `generate_tasks` | 从路线图生成任务 |
| `get_today_tasks` | 获取今日任务 |

### 流程

```
1. generate_tasks()
2. get_today_tasks()
```

### 前置条件

- `profile.plan.roadmap` 已生成（save_roadmap 已调用）

### 输出

- `profile.tasks`：任务列表
  - 每个任务包含 `id`、`name`、`deadline`、`status`

---

## 阶段 5：执行

### 目标

用户执行任务，打卡记录进度。

### 工具

| 工具 | 作用 |
|------|------|
| `get_today_tasks` | 获取今日任务 |
| `checkin_task` | 打卡任务 |

### 流程

```
1. get_today_tasks()
2. checkin_task(task_id="task_001", status="completed", notes="提前完成")
```

### 前置条件

- `profile.tasks` 已生成（generate_tasks 已调用）

### 输出

- `profile.checkins`：打卡记录
- 任务状态更新（pending → completed）

---

## 阶段 6：洞察调整

### 目标

分析进度，提出调整建议。

### 工具

| 工具 | 作用 |
|------|------|
| `trigger_insight` | 触发洞察分析 |
| `apply_insight` | 应用洞察结果 |
| `get_progress` | 查看进度 |
| `suggest_adjustment` | 提出调整建议 |

### 流程

```
1. trigger_insight(trigger_type="proactive")
2. apply_insight(insight_json='{"status":"on_track", ...}')
```

### 前置条件

- `profile.tasks` 已生成

### 输出

- `profile.adjustments`：调整记录

### 触发时机

| 类型 | 触发时机 | 示例 |
|------|----------|------|
| 阶段审计 | 完成阶段后 | 完成实习后，评估含金量 |
| 事件触发 | 用户报告事件 | "拿到大厂面试" |
| 主动检查 | 定期检查 | 超期任务检测 |

---

## 状态查询

### 工具

| 工具 | 作用 |
|------|------|
| `get_workflow_status` | 获取当前工作流状态 |

### 使用时机

- 用户开始对话时
- LLM 不确定下一步时
- 需要查看整体状态时

### 返回值

```json
{
  "phase": "analysis",
  "completed_steps": ["start_session", "intake(who)", "intake(have)", "intake(want)", "finalize_profile"],
  "next_step": "analyze_gaps",
  "task_stats": {"total": 0, "completed": 0, "overdue": 0}
}
```
