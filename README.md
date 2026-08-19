# Career Kit

AI 驱动的职业规划 MCP 服务器。建档、差距分析、路线图、日程表——全程本地运行，数据不离开你的电脑。

## 它能做什么

```
你：我是计算机应届生，想在12月前拿到前端offer
Career Kit：建立档案 → 分析差距 → 生成路线图 → 输出每日日程

你：今天把 React 教程刷完了
Career Kit：记录进度 → 调整路线图 → 生成明天的新日程
```

## 核心流程

```
start_session → intake（循环）→ finalize_profile
                                    ↓
                              analyze_gaps → generate_roadmap → generate_schedule
                                                                    ↓
                                                              track_progress →（回到 analyze）
```

## MCP 工具

| 工具 | 作用 |
|------|------|
| `start_session` | 初始化新的职业规划会话 |
| `intake` | 逐步填充档案（who/have/want） |
| `finalize_profile` | 确认档案完整，生成摘要，解锁分析工具 |
| `analyze_gaps` | 对比现状与目标，拉取市场数据 |
| `generate_roadmap` | 基于差距分析生成分阶段路线图 |
| `generate_schedule` | 路线图拆解为日/周日程，支持导出 ICS |
| `track_progress` | 记录进度，自动调整后续计划 |
| `search_market` | 搜索岗位、薪资、面试信息 |

## 数据模型

骨架固定，内容自由。LLM 根据每个用户的具体情况决定每个 section 里放什么：

```json
{
  "who": {},     // 你是谁——LLM 自由填充
  "have": {},    // 你有什么——技能、经历、资源
  "want": {},    // 你想要什么——目标岗位、行业、薪资
  "gap": {},     // 差距是什么——analyze_gaps 自动生成
  "plan": {}     // 怎么走——generate_roadmap 自动生成
}
```

只有这 5 个 section 是固定的，内部字段完全由 LLM 根据对话内容灵活组织。

## 安装

```bash
pip install career-kit
```

## 在 Claude Code 中使用

添加到 MCP 配置：

```json
{
  "mcpServers": {
    "career-kit": {
      "command": "career-kit"
    }
  }
}
```

## 在 Cursor / Windsurf / Continue 中使用

Career Kit 使用标准 MCP 协议，任何 MCP 客户端都能连接。

## 隐私

所有数据存储在本地 `~/.career-kit/`，不会发送到任何外部服务器。

## 开源协议

MIT
