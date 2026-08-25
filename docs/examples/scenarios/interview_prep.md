# 面试准备场景

> 拿到面试后的准备流程

## 用户背景

- 已有：AI Agent 工程师面试机会
- 目标：准备面试，提高通过率

## 工作流

### 1. 触发洞察

```
trigger_insight(trigger_type="event", event_description="拿到字节跳动 AI Agent 工程师面试")
```

### 2. 应用调整

```
apply_insight(insight_json='{
  "status": "need_adjustment",
  "summary": "需要添加面试冲刺阶段",
  "adjustment_needed": true,
  "adjustment_reason": "用户拿到大厂面试，需要针对性准备",
  "changes": [
    {
      "type": "add_phase",
      "phase": {
        "name": "面试冲刺",
        "duration": "1周",
        "milestones": [
          {"name": "公司研究", "duration": "1天"},
          {"name": "岗位要求分析", "duration": "1天"},
          {"name": "面试题准备", "duration": "3天"},
          {"name": "模拟面试", "duration": "2天"}
        ]
      }
    }
  ],
  "user_message": "恭喜拿到面试！我已为你添加面试冲刺阶段。"
}')
```

### 3. 搜索面试信息

```
fetch_company_jobs(company="nowcoder", params='{"keyword":"Agent 开发", "filter_company":"字节跳动"}')
search_knowledge(query="字节跳动 AI Agent 面经")
```

### 4. 生成面试任务

```
generate_tasks()
get_today_tasks()
```

### 5. 打卡执行

```
checkin_task(task_id="task_interview_001", status="completed", notes="完成公司研究")
checkin_task(task_id="task_interview_002", status="completed", notes="完成岗位要求分析")
```
