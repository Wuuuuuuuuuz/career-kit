# 工作流详解

> Career Kit 完整工作流、前置条件、输入输出
>
> 核心理念：**顺序归产品，时间归用户**——不为任务设定时限。

## 工作流总览

```
建档 → 分析 → 规划 → 任务执行 → 打卡 → 阶段审计/事件洞察 → 循环
```

## 阶段 1：建档

### 目标

建立用户职业档案，摸清用户真实水平（简历有美化成分）、了解用户是谁、有什么、想要什么。

### 工具

| 工具 | 作用 |
|------|------|
| `start_session` | 初始化会话 |
| `parse_resume` | 解析简历文件 |
| `intake` | 填充档案（who/have/want） |
| `finalize_profile` | 确认档案 |
| `explore_goals` | 无目标时引导选方向（三轴定位：能力×兴趣×真实市场数据） |
| `import_jd` / `import_jd_file` | 导入 JD（可选） |

### 流程

```
1. start_session()
2. intake(section="who", data='{"name":"张三", "education":"计算机本科"}')
3. intake(section="have", data='{"skills":["Python"], "skill_evidence":[{"skill":"Python","evidence":"电商后端项目","confidence":"high"}]}')
   // 关键技能要追问证据：做过什么项目？讲一个难点？
4. 确定目标：
   - 有明确目标 → intake(section="want", data='{"target_role":"AI Agent 工程师", "salary":"20k-30k"}')
   - 没有目标/方向模糊 → explore_goals() 对话引导选定，再 intake(section="want") 落定
   - 有 JD 文件 → import_jd_file(file_path) → import_jd()
5. finalize_profile()
```

### 前置条件

- 无

### 输出

- `profile.summary`：档案摘要
- `profile.section_updated_at`：各 section 更新时间（目标变更检测依据）

---

## 阶段 2：分析

### 目标

对比用户现状与目标，基于真实数据找出差距。

### 工具

| 工具 | 作用 |
|------|------|
| `list_data_sources` | 查看可用企业数据源 |
| `get_scraper_guide` | 读取指定数据源教程 |
| `fetch_company_jobs` | 抓取真实岗位（含薪资范围），自动写入知识库 |
| `fetch_jd_detail` | 获取 JD 全文 |
| `search_knowledge` | 检索本地知识库 |
| `analyze_gaps` | 获取分析方法论 |
| `save_gap_analysis` | 保存分析结果 |

### 流程

```
1. list_data_sources()                              // 查看可用企业
2. get_scraper_guide(company="bytedance")           // 首次使用前读教程
3. fetch_company_jobs(company="bytedance", params='{"keyword":"AI Agent"}')  // 必须调用
4. fetch_jd_detail(url="...")                       // 获取 JD 全文
5. search_knowledge(query="AI Agent 面经")          // 补充本地资料
6. analyze_gaps()
7. save_gap_analysis(gap_json='{"match_score":65, "skill_gaps":[...]}')
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
3. **不要凭空分析**：差距必须基于真实市场数据；薪资行情从岗位搜索结果的 salary 字段汇总

---

## 阶段 3：规划

### 目标

基于差距分析，生成分阶段路线图。只定顺序与完成标准，不定时间。

### 工具

| 工具 | 作用 |
|------|------|
| `generate_roadmap` | 获取路线图方法论 |
| `save_roadmap` | 保存路线图 |

### 流程

```
1. generate_roadmap()
2. save_roadmap(roadmap_json='{"strategy_summary":"...", "phases":[...]}')
```

### 前置条件

- `profile.gap` 已生成（save_gap_analysis 已调用）

### 输出

- `profile.plan.roadmap`：路线图
  - `phases`：阶段列表（id 由系统规范化为 phase_N）
  - 每个阶段包含 `name`、`goal`、`kpi`、`resume_value`、`milestones`
  - 任务 schema：`{name, description, priority}`——**不含任何时长字段**

### 关键规则

1. **基于真实数据规划**：路线图中的任务应基于市场真实要求
2. **不输出时长字段**：duration/estimated_days 一律不要；KPI 不设时间承诺
3. **里程碑要有 done_criteria**：完成与否看标准不看日历
4. 用户想要日程 → 在对话中直接写 markdown/HTML 文档交付，时间由用户自己填

---

## 阶段 4：任务执行与打卡

### 目标

将路线图转化为可执行的任务列表，关卡式推进。

### 工具

| 工具 | 作用 |
|------|------|
| `generate_tasks` | 从路线图生成任务（重建时历史进度沉淀为能力证据） |
| `get_next_tasks` | 当前阶段的下一步任务 |
| `checkin_task` | 打卡任务 |

### 流程

```
1. generate_tasks()
2. get_next_tasks()
3. checkin_task(task_id="task_001", status="completed", notes="练习题也做了")
```

### 前置条件

- `profile.plan.roadmap` 已生成（save_roadmap 已调用）

### 输出

- `profile.tasks`：任务列表
  - 每个任务包含 `id`、`name`、`description`、`phase_id`、`status`、`priority`
- `profile.have.capability_evidence`：完成任务自动沉淀的能力证据

---

## 阶段 5：洞察调整

### 目标

阶段完成后审计，用户报告事件时重估计划。

### 工具

| 工具 | 作用 |
|------|------|
| `trigger_insight` | 触发洞察分析 |
| `apply_insight` | 应用洞察结果 |
| `get_progress` | 查看进度 |

### 流程

```
1. trigger_insight(trigger_type="stage_audit")
2. apply_insight(insight_json='{"trigger_type":"stage_audit", "status":"on_track", ...}')
```

### 前置条件

- `profile.tasks` 已生成

### 输出

- `profile.adjustments`：调整记录（类型仅 add_task/remove_task/modify_task）
- `profile.audited_phases`：已审计阶段（每阶段只审计一次）

### 触发时机

| 类型 | 触发时机 | 示例 |
|------|----------|------|
| 阶段审计 stage_audit | 完成阶段后 | 完成实习后，评估含金量 |
| 事件触发 event | 用户报告事件 | "拿到大厂面试" |

> 「主动检查/超期压缩」已移除——产品不为任务设定时限，不存在超期。

---

## 产出物

| 工具 | 产出 |
|------|------|
| `export_dashboard` | 自包含 HTML 阶段仪表盘（内嵌数据快照，双击即看） |
| 对话直接编写 | 日程表 markdown/HTML 文档（时间由用户自己填） |

---

## 状态查询

### 工具

| 工具 | 作用 |
|------|------|
| `get_workflow_status` | 获取当前工作流状态 + 目标变更检测 |

### 使用时机

- 用户开始对话时
- LLM 不确定下一步时
- want/target_jd 在路线图之后被更新过（提示重新 analyze_gaps）
