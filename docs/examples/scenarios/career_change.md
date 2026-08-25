# 转行场景

> 前端工程师转行 AI Agent 工程师

## 用户背景

- 当前：前端工程师，1年经验
- 目标：AI Agent 工程师
- 期望薪资：20k-30k
- 目标城市：上海

## 工作流

### 1. 建档

```
start_session()
intake(section="who", data='{"name":"张三", "education":"计算机本科", "status":"在职"}')
intake(section="have", data='{"skills":["JavaScript", "React", "Node.js"], "experience":"1年前端开发"}')
intake(section="want", data='{"target_role":"AI Agent 工程师", "salary":"20k-30k", "city":"上海"}')
finalize_profile()
```

### 2. 分析

```
analyze_gaps()
list_data_sources()
fetch_company_jobs(company="boss", params='{"keyword":"AI Agent", "city":"上海"}')
fetch_jd_detail(url="...")
save_gap_analysis(gap_json='{
  "match_score": 45,
  "skill_gaps": [
    {"skill": "Python", "priority": "high", "source": "BOSS直聘 JD"},
    {"skill": "LLM", "priority": "high", "source": "BOSS直聘 JD"},
    {"skill": "LangChain", "priority": "medium", "source": "BOSS直聘 JD"},
    {"skill": "RAG", "priority": "medium", "source": "BOSS直聘 JD"}
  ],
  "priority_actions": [
    "学习 Python 基础",
    "学习 LLM 基础概念",
    "学习 LangChain 框架"
  ]
}')
```

### 3. 规划（只定顺序与标准，不定时间）

> save_roadmap 的 phases 中不要写 duration 字段，里程碑用 done_criteria 表达完成标准。
>
> generate_schedule / save_schedule 已下线——用户想要日程时，
> 在对话中直接把任务写成 markdown/HTML 文档交付，时间由用户自己填。

### 4. 任务执行

```
generate_tasks()
get_next_tasks()
checkin_task(task_id="task_001", status="completed", notes="Python 基础学完")
```

### 5. 洞察调整（阶段完成后审计）

```
trigger_insight(trigger_type="stage_audit")
apply_insight(insight_json='{"trigger_type":"stage_audit", "status":"on_track", "summary":"进度正常", "adjustment_needed":false}')
```
