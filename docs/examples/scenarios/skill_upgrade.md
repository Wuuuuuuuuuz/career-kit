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
fetch_company_jobs(company="bytedance", params='{"keyword":"高级 AI Agent"}')
fetch_jd_detail(url="...")
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

### 3. 规划（只定顺序与标准，不定时间）

```
generate_roadmap()
save_roadmap(roadmap_json='{
  "strategy_summary": "围绕多Agent系统深入，用项目落地，最后冲刺求职",
  "phases": [
    {
      "type": "learn",
      "name": "深入学习",
      "goal": "补齐多Agent系统、Agent评估与性能优化",
      "kpi": {"metric": "完成学习并产出笔记", "target": "3 个专题", "evidence": "技术笔记"},
      "resume_value": "",
      "milestones": [
        {"name": "多Agent系统", "done_criteria": "能设计双Agent协作架构"},
        {"name": "Agent评估", "done_criteria": "能搭建自动化评估流水线"},
        {"name": "性能优化", "done_criteria": "现有项目关键指标提升有数据"}
      ]
    },
    {
      "type": "project",
      "name": "项目实战",
      "goal": "用项目巩固所学",
      "kpi": {"metric": "GitHub star", "target": "30+", "evidence": "仓库链接"},
      "resume_value": "独立开发多Agent协作系统与性能优化实践",
      "milestones": [
        {"name": "多Agent项目", "done_criteria": "端到端 demo 可运行"},
        {"name": "性能优化项目", "done_criteria": "优化前后对比报告"}
      ]
    },
    {
      "type": "learn",
      "name": "求职准备",
      "goal": "简历与面试就绪",
      "kpi": {"metric": "模拟面试", "target": "连续 2 次通过", "evidence": "模拟记录"},
      "resume_value": "",
      "milestones": [
        {"name": "简历优化", "done_criteria": "ATS 关键词全覆盖且项目量化"},
        {"name": "面试题准备", "done_criteria": "高频题能脱稿讲解"}
      ]
    }
  ]
}')
```

### 4. 任务执行

```
generate_tasks()
get_next_tasks()
checkin_task(task_id="task_001", status="completed", notes="多Agent系统学习完成")
```

### 5. 洞察调整（阶段完成后审计）

```
trigger_insight(trigger_type="stage_audit")
apply_insight(insight_json='{"trigger_type":"stage_audit", "status":"ahead", "summary":"进度超前，可以加深难度", "adjustment_needed":true, "changes":[{"type":"add_task", "details":{"name":"多Agent系统深入研究"}}]}')
```

### 用户想要日程表？

直接在对话中把当前阶段的任务写成 markdown/HTML 文档交给用户，
时间块留空由用户自己填——系统不存储日程。
