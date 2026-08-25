# 技能提升场景

> 在职人员提升技能

## 用户背景

- 当前：AI Agent 工程师，1年经验
- 目标：提升技能，争取晋升或跳槽

## 工作流

### 1. 建档

```
start_session()
intake(section="who", data='{"name":"李四", "education":"计算机硕士", "status":"在职"}')
intake(section="have", data='{"skills":["Python", "LangChain", "RAG"], "experience":"1年AI Agent开发"}')
intake(section="want", data='{"target_role":"高级 AI Agent 工程师", "salary":"35k-50k", "city":"北京"}')
finalize_profile()
```

### 2. 分析

```
analyze_gaps()
search_market(query="高级 AI Agent 工程师 技能要求")
search_market(query="AI Agent 技术趋势 2025")
save_gap_analysis(gap_json='{
  "match_score": 70,
  "skill_gaps": [
    {"skill": "多Agent系统", "priority": "high", "source": "BOSS直聘 JD"},
    {"skill": "Agent评估", "priority": "medium", "source": "BOSS直聘 JD"},
    {"skill": "性能优化", "priority": "medium", "source": "BOSS直聘 JD"}
  ],
  "priority_actions": [
    "学习多Agent系统设计",
    "学习Agent评估方法",
    "优化现有项目性能"
  ]
}')
```

### 3. 规划

```
generate_roadmap()
save_roadmap(roadmap_json='{
  "phases": [
    {
      "name": "深入学习",
      "duration": "3周",
      "milestones": [
        {"name": "多Agent系统", "duration": "1周"},
        {"name": "Agent评估", "duration": "1周"},
        {"name": "性能优化", "duration": "1周"}
      ]
    },
    {
      "name": "项目实战",
      "duration": "2周",
      "milestones": [
        {"name": "多Agent项目", "duration": "1周"},
        {"name": "性能优化项目", "duration": "1周"}
      ]
    },
    {
      "name": "求职准备",
      "duration": "1周",
      "milestones": [
        {"name": "简历优化", "duration": "2天"},
        {"name": "面试题准备", "duration": "5天"}
      ]
    }
  ]
}')
generate_schedule(scope="this_week")
save_schedule(schedule_json='{"schedule":[...]}')
```

### 4. 任务管理

```
generate_tasks()
get_today_tasks()
checkin_task(task_id="task_001", status="completed", notes="多Agent系统学习完成")
```

### 5. 洞察调整

```
trigger_insight(trigger_type="proactive")
apply_insight(insight_json='{"status":"ahead", "summary":"进度超前，可以加深难度", "adjustment_needed":true, "changes":[{"type":"add_task", "task":{"name":"多Agent系统深入研究", "estimated_days":3}}]}')
```
