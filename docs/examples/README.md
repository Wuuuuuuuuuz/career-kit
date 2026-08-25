# 示例目录

> Career Kit 完整工作流示例和场景示例

## 快速开始

- [完整工作流示例](full_workflow.md)：从建档到任务管理的完整流程
- [场景示例](scenarios/)：常见场景的处理方式

## 完整工作流示例

### 场景：应届生转行 AI Agent 工程师

```
1. start_session()
2. intake(section="who", data='{"name":"张三", "education":"计算机本科", "status":"应届生"}')
3. intake(section="have", data='{"skills":["Python", "React"], "experience":"1年前端实习"}')
4. intake(section="want", data='{"target_role":"AI Agent 工程师", "salary":"20k-30k", "city":"上海"}')
5. finalize_profile()
6. analyze_gaps()
7. list_company_jobs()
8. fetch_company_jobs(company="bytedance", params='{"keyword":"AI Agent"}')
9. save_gap_analysis(gap_json='{"match_score":65, "skill_gaps":[{"skill":"LLM", "source":"BOSS直聘 JD"}, ...]}')
10. generate_roadmap()
11. save_roadmap(roadmap_json='{"phases":[...]}')
12. generate_schedule(scope="this_week")
13. save_schedule(schedule_json='{"schedule":[...]}')
14. generate_tasks()
15. get_today_tasks()
16. checkin_task(task_id="task_001", status="completed")
```

## 场景示例

### 转行场景

- [前端转 AI](scenarios/career_change.md)：前端工程师转行 AI Agent 工程师

### 面试准备场景

- [面试冲刺](scenarios/interview_prep.md)：拿到面试后的准备流程

### 技能提升场景

- [技能升级](scenarios/skill_upgrade.md)：在职人员提升技能

## 示例数据

- [示例档案](data/sample_profile.json)：用户档案示例
- [示例差距分析](data/sample_gap.json)：差距分析结果示例
- [示例路线图](data/sample_roadmap.json)：路线图示例
