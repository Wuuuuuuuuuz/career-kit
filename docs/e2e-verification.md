# Career Kit 端到端验证手册

> 真实接入 MCP 跑全流程，验证所有 30 个工具。按场景一步步照做，每步有预期结果与验证点。
>
> 核心理念：**顺序归产品，时间归用户**——不为任务设定时限；所有分析基于真实数据，绝不编造。

---

## 0. 准备工作

### 0.1 接入 MCP

| Agent | 接入方式 |
|-------|----------|
| Claude Code | `claude mcp add career-kit -- python -m src.server`（在项目目录执行） |
| opencode | `opencode.json` 中加入 `{"mcp": {"career-kit": {"type": "local", "command": ["python", "-m", "src.server"], "enabled": true}}}` |
| Cursor / Windsurf | MCP 设置手动添加：command=`python`，args=`["-m", "src.server"]` |

验证接入：新会话输入 `/career-kit`，收到「欢迎使用 Career Kit」欢迎手册即成功。

### 0.2 隔离数据（推荐，避免污染真实档案）

用独立数据目录跑测试，结束后可整体删除：

- **Windows PowerShell**：`$env:CAREER_KIT_DATA_DIR = "$env:TEMP\ck_e2e_test"; python -m src.server`
- **macOS / Linux**：`CAREER_KIT_DATA_DIR=/tmp/ck_e2e_test python -m src.server`

> ⚠️ MCP 客户端注册时也需带上该环境变量。若嫌麻烦，直接跑真实目录亦可——档案管理功能（场景 B）本就是为此设计的。

### 0.3 约定

- 场景 A 用 `default` 档案；场景 B 新建 `alice` / `bob` 档案。
- 每个验证点标注 ✅ 表示通过，❌ 表示失败（请记录失败信息反馈）。

---

## 1. 场景总览

| 场景 | 覆盖功能 | 覆盖工具 |
|------|----------|----------|
| A：零基础小白全流程 | 建档 → 目标探索 → 差距分析 → 路线图 → 任务 → 打卡 → 洞察 → 产出 | 约 20 个 |
| B：多档案管理 | 档案列表/切换/回收站删除/恢复 | 5 个 |
| C：数据获取与守卫 | 真实抓取 + 边界守卫 | 约 10 个 |

---

## 2. 场景 A：零基础小白 → 选定方向 → 全链路执行

> 角色设定：用户是**零基础小白**（应届、不会编程），不知道想做什么——验证目标探索 + 全流程贯通。

### 第 1 步：启动会话

**操作**：`start_session`

**预期**：
- 返回欢迎手册（职业教练角色 + 完整流程）
- 含 `当前档案：default`

**验证点**：✅ 欢迎手册含「顺序归产品，时间归用户」 ✅ 标注当前档案

### 第 2 步：建档（who / have）

**操作**：
```
intake(section="who", data='{"name":"测试小白","status":"应届生","education":"本科 市场营销"}')
intake(section="have", data='{"skills":[],"experience_level":"零基础","interests":["对AI感兴趣但完全不会编程"]}')
```

**预期**：每条返回 `已记录到「who/have」。当前档案版本：vN`（版本递增）

**验证点**：✅ 版本号递增 ✅ 零基础如实记录（skills 空、experience_level=零基础，未美化）

### 第 3 步：确认档案（应提示目标缺失）

**操作**：`finalize_profile`

**预期**：
- 返回档案摘要（身份 + 现状）
- 含 `ℹ️ 目标缺失` 提醒，指向 `explore_goals`

**验证点**：✅ 目标缺失提醒出现 ✅ 提示用 explore_goals 选方向

### 第 4 步：状态机引导（应指向 explore_goals）

**操作**：`get_workflow_status`

**预期**：`**下一步**：explore_goals（尚无明确目标——先用三轴定位选定方向，再 analyze_gaps）`

**验证点**：✅ 状态机把无目标用户导向目标选择（而非 analyze_gaps）

### 第 5 步：差距分析守卫（无目标应被拒绝）

**操作**：`analyze_gaps`

**预期**：结构化错误 `isError: true`，`code: MISSING_DATA`，`details.suggestion` 含 `explore_goals`

**验证点**：✅ 无目标时拒绝分析，不产出"无目标差距报告"

### 第 6 步：目标探索（explore_goals）

**操作**：`explore_goals`

**预期**：
- 返回 JSON：`methodology.name == "目标选择"`
- methodology 含四阶段（probe_reality / gather_market / propose_directions / decide）
- instructions 含「fetch_company_jobs」「intake(section='want')」

**验证点**：✅ 方法论返回 ✅ instructions 强调真实数据（不编造热门方向）

### 第 7 步：对话选定方向（模拟用户）

**操作**（与 AI 对话）：
1. AI 问兴趣/约束（Genie Goal 式）→ 回答："我想做能跟 AI 打交道的工作，但不写代码"
2. AI 调用 `fetch_company_jobs` 抓真实岗位（如搜 "AI 产品" / "AI 运营"）支撑候选
3. AI 给出 2-3 个候选方向（标注假设 + Fit Filters + 零基础友好度）
4. 用户选定一个（如 "AI 产品经理（零基础友好方向）"）

**验证点**：
- ✅ AI 先抓真实数据再给方向（看 AI 是否调了 fetch_company_jobs）
- ✅ 候选方向带「适合/否决信号」与「零基础友好度」
- ✅ 没有让用户做测评题（霍兰德/MBTI 问卷）
- ✅ 零基础如实对待，没有假装用户会编程

### 第 8 步：落定目标（intake want）

**操作**：
```
intake(section="want", data='{"target_role":"AI 产品经理（入门）","interest":"对AI感兴趣","constraints":"不写代码","direction_confidence":8,"experience_level":"零基础"}')
```

**预期**：`已记录到「want」。当前档案版本：vN`

**验证点**：✅ 目标落定 ✅ experience_level 如实为零基础

### 第 9 步：重复探索守卫（已有目标应提示确认）

**操作**：`explore_goals`

**预期**：返回 `⚠️ 档案中已有目标：...` 提示（含 target_role），**不**直接返回方法论

**验证点**：✅ 已有目标时守卫拦截 ✅ 提示"直接走 analyze_gaps 或明确换方向"

### 第 10 步：差距分析（应放行）

**操作**：`analyze_gaps`

**预期**：返回 JSON，含 `methodologies`（resume_screening + interview_prep）与 instructions

**验证点**：✅ 有目标后放行 ✅ 返回两个方法论

### 第 11 步：抓取真实数据（差距分析的数据基础）

**操作**（对话引导 AI 执行）：
```
list_data_sources
get_scraper_guide(company="bytedance")   # 或 boss / nowcoder
fetch_company_jobs(company="bytedance", params='{"keyword":"AI 产品"}')
```

**预期**：
- `list_data_sources`：列出已注册企业（boss/bytedance/nowcoder）及参数
- `get_scraper_guide`：返回该企业使用教程
- `fetch_company_jobs`：返回岗位列表（标题/地点/薪资/链接）或**如实报错**

**验证点**：
- ✅ 三个数据源工具返回正常
- ✅ 若抓取失败：返回结构化错误 + 恢复建议，**绝不编造岗位数据**（这本身是重要验证点）
- ✅ 成功时结果自动写入知识库（之后 `search_knowledge` 可查到）

### 第 12 步：保存差距分析

**操作**（AI 分析后调用）：
```
save_gap_analysis(gap_json='{"match_score":20,"match_level":"差距大","strengths":[],"resume_optimization":{"ats_keywords":[],"missing_keywords":["产品思维","AI基础认知"],"resume_tips":["..."]},"interview_preparation":{"must_prepare":[],"project_deep_dive":[],"system_design_topics":[],"behavioral_questions":[],"study_plan":{}},"skill_gaps":[{"skill":"产品思维","priority":"high","current_level":"无","required_level":"入门","how_to_improve":"系统学习产品方法论","source":"字节跳动 JD"}],"priority_actions":[{"action":"学习产品入门课程","impact":"high","difficulty":"low"}],"market_context":"AI 产品岗位需求增长"}')
```

**预期**：返回 `差距分析已保存` + 报告，`next_steps: ["generate_roadmap"]`

**验证点**：✅ 保存成功 ✅ 返回含 skill_gaps 报告 ✅ 提示下一步

### 第 13 步：生成路线图

**操作**：`generate_roadmap`

**预期**：返回 roadmap 方法论 + instructions（含「起点对齐」「jd 三件套」纪律）

**验证点**：✅ 方法论返回 ✅ instructions 强调 jd 三件套（有据填 JD，无据占位）

### 第 14 步：保存路线图（验证 jd 三件套 + HTML 交付物）

**操作**：
```
save_roadmap(roadmap_json='{"strategy_summary":"零基础先学产品基础，再做作品集，最后投实习","phases":[{"type":"learn","name":"产品基础学习","goal":"掌握产品思维与工具","kpi":{"metric":"完成入门课程","target":"100%","evidence":"能画出完整流程图"},"milestones":[{"name":"产品入门","done_criteria":"能讲清产品从0到1","tasks":[{"name":"学习产品方法论","priority":"high"},{"name":"练习原型工具","priority":"medium"}]}]},{"type":"project","name":"AI 产品作品集","goal":"做1-2个可展示的AI产品分析/设计项目","kpi":{"metric":"作品集项目数","target":"2个","evidence":"含用户调研与原型"}, "resume_value":"独立完成2个AI产品设计项目（调研+原型+方案）","milestones":[{"name":"项目1","done_criteria":"完成项目并输出文档","tasks":[{"name":"选AI产品选题","priority":"high"}]}]},{"type":"intern","name":"某公司 AI 产品实习","company":"某公司","rationale":"对零基础友好，AI布局重","jd_status":"pending_user_import","confirmed":false,"resume_value":"AI产品实习经历","milestones":[{"name":"投递","done_criteria":"投出10份简历","tasks":[{"name":"准备简历","priority":"high"}]}]}]}')
```

**预期**：
- 返回 `路线图已保存` + 报告
- 含 ⚠️ 依据待确认（intern 阶段占位未确认 → 提示确认「先占位后补JD」）
- 返回路线图 HTML 路径（`career_kit_roadmap.html`，双击即看）

**验证点**：
- ✅ 保存成功 ✅ 占位阶段（pending_user_import + confirmed=false）被软校验提示
- ✅ HTML 交付物自动生成
- ✅ 全程无时长字段（duration/estimated_days 未出现）

### 第 15 步：生成任务

**操作**：`generate_tasks`

**预期**：`已从路线图生成 N 个任务` + 任务列表（含 phase_id、priority），`next_steps: ["get_next_tasks"]`

**验证点**：✅ 任务数量与路线图里程碑任务一致 ✅ 阶段 id 关联正确

### 第 16 步：查看下一步任务（关卡式 + 全流程概览）

**操作**：`get_next_tasks`

**预期**：
- 顶部 `## 🗺️ 全流程`（所有阶段 + 完成状态 + 当前定位）
- 中部 `## 🎯 当前阶段：产品基础学习（0/2，0%）` + 接下来做（任务 + ID）

**验证点**：✅ 全流程概览 ✅ 当前阶段任务带 ID ✅ 无时限压力提示

### 第 17 步：打卡（能力证据沉淀）

**操作**：
```
checkin_task(task_id="task_001", status="completed", notes="看完产品入门课并做了笔记")
```

**预期**：
- `✅ 已打卡：{任务名}`
- 进度概览（阶段进度提升）
- 完成后 get_next_tasks 显示进度变化

**验证点**：
- ✅ 打卡成功 ✅ 能力证据自动沉淀（之后 export_dashboard 可看到）
- ✅ 打卡返回值提示「完成得轻松可加深难度或推进下一项」

### 第 18 步：阶段审计（完成阶段后触发）

**操作**（对话引导）：先完成当前阶段全部任务（逐个 checkin_task），然后：
```
trigger_insight(trigger_type="stage_audit")
```

**预期**：
- 完成全部任务后，`checkin_task` 返回 `🎯 恭喜！你完成了阶段「XXX」的全部任务` + 建议触发审计
- `trigger_insight` 返回 prompt + output_format（on_track/behind/ahead/need_adjustment）

**验证点**：✅ 阶段完成检测 ✅ 审计触发（每阶段只审计一次——audited_phases 去重）

### 第 19 步：应用洞察（调整任务）

**操作**：
```
apply_insight(insight_json='{"trigger_type":"stage_audit","status":"on_track","summary":"基础阶段完成","insights":["学习速度正常"],"adjustment_needed":true,"adjustment_type":"auto","adjustment_reason":"完成标准达成","changes":[{"type":"add_task","details":{"name":"加练一个原型项目"}}],"user_message":"继续保持"}')
```

**预期**：`已应用调整` + adjustment 记录

**验证点**：✅ 新增任务成功 ✅ `get_progress` 可看到调整历史

### 第 20 步：进度与产出

**操作**：
```
get_progress
export_dashboard(mode="progress")
export_dashboard(mode="roadmap")
```

**预期**：
- `get_progress`：进度概览 + 调整历史
- `export_dashboard(mode="progress")`：生成 `career_kit_dashboard.html`（总进度+阶段进度+接下来做+能力证据+调整历史）
- `export_dashboard(mode="roadmap")`：生成 `career_kit_roadmap.html`（职业地图：阶段/KPI/里程碑/公司/依据徽标/执行进度）

**验证点**：
- ✅ get_progress 显示任务统计与调整历史
- ✅ 两个 HTML 均生成、双击可打开
- ✅ roadmap HTML 含「待导入真实 JD」占位徽标（intern 阶段）与「起点层级」

---

## 3. 场景 B：多档案管理

> 验证一台电脑多人/多方案场景：建档、切换、回收站式删除、恢复。

### 第 1 步：查看档案列表

**操作**：`list_profiles`

**预期**：列出 `default`（⭐ 当前使用）+ 身份/目标/版本/更新时间

**验证点**：✅ 列表含当前使用标记

### 第 2 步：新建并切换档案

**操作**：
```
switch_profile(profile_name="alice")
```

**预期**：`档案「alice」不存在`（MISSING_DATA）——需要先建档

**操作**：对话引导 AI：
1. `switch_profile` 切换后提示不存在 → 让 AI 引导先建 alice 档案
2. 实际建档：**切换前先给 alice 造档案**——对话中用 `intake` 填 who 时，注意 intake 写入的是当前 active 档案。

> ⚠️ 这里暴露一个真实交互：目前**没有"新建档案"工具**，alice 档案需通过先 `switch_profile` 到已存在的档案，或直接写文件。若你想造多份档案，最简单方式：当前 active=default 时，用 `merge_section` 直接给指定档案名写入（如测试用 `profile.merge_section("who", ..., "alice")`），或复制 default.json 为 alice.json。

**推荐验证路径**：
1. 在文件系统复制 `default.json` → `alice.json`（或对话让 AI 用代码方式生成）
2. `switch_profile(profile_name="alice")` → 预期 `已切换到档案「alice」` + 摘要

**验证点**：
- ✅ switch 不存在的档案返回结构化错误（不污染当前 active）
- ✅ switch 成功返回新档案摘要
- ✅ 切换后 `get_workflow_status` 标注 `当前档案：alice`

### 第 3 步：数据隔离验证

**操作**：在 alice 档案下 `intake(section="have", data='{"skills":["Python"]}')`，然后切回 default 看 default 没被污染

**预期**：default 的 have 不含 Python

**验证点**：✅ 多档案数据隔离

### 第 4 步：回收站式删除（需确认）

**操作**：
```
delete_profile(profile_name="alice")          # 不带 confirm
delete_profile(profile_name="alice", confirm="true")
```

**预期**：
- 不带 confirm → 返回确认提示（不删除）
- confirm="true" → `已删除档案「alice」（移入回收站，可恢复）` + 回收站路径 + 剩余档案

**验证点**：
- ✅ 删除需显式确认（confirm="true"）
- ✅ 删除进回收站（trash/），非直接 unlink
- ✅ 删除当前 active 档案也可（回收站式安全），active 自动回退 default

### 第 5 步：查看回收站并恢复

**操作**：
```
list_trash
restore_profile(profile_name="alice")
```

**预期**：
- `list_trash`：列出回收站项（`alice`，含删除时间）
- `restore_profile`：`已恢复档案「alice」` + 摘要

**验证点**：
- ✅ 回收站可查看
- ✅ 恢复后数据完整（身份/目标都在）
- ✅ 恢复后可 `switch_profile` 继续使用

### 第 6 步：恢复冲突守卫

**操作**：删除 alice → 重建 alice（对话中 intake 填了新的）→ 再 restore alice

**预期**：`restore_profile` 返回错误 `档案「alice」已存在，拒绝覆盖`

**验证点**：✅ 恢复不覆盖新数据（防误恢复）

### 第 7 步：非法档案名守卫

**操作**：`switch_profile(profile_name="../evil")` 或 `delete_profile(profile_name="../evil")`

**预期**：结构化错误 `INVALID_SECTION`（非法档案名：只允许字母/数字/下划线/连字符）

**验证点**：✅ 路径穿越被拦截

---

## 4. 场景 C：数据获取与守卫

### 第 1 步：数据源清单与教程

**操作**：
```
list_data_sources
get_scraper_guide(company="boss")
```

**预期**：
- `list_data_sources`：列出 boss（BOSS直聘）/bytedance（字节跳动）/nowcoder（牛客网）及各自搜索参数
- `get_scraper_guide(company="boss")`：返回 BOSS 使用教程（含登录要求）

**验证点**：✅ 数据源清单 ✅ 教程可读（返回"登录要求"说明即正确）

### 第 2 步：知识库检索（先抓后查）

**操作**：`search_knowledge(query="AI 产品")`

**预期**：
- 若场景 A 已抓取过 → 返回相关结果（含来源文件路径）
- 若未抓取 → 返回 `知识库中暂无相关资料` + 下一步建议（fetch_company_jobs）

**验证点**：✅ 诚实返回（无结果就说无，不编造）✅ 引导走抓取链路

### 第 3 步：JD 导入守卫

**操作**：
```
import_jd(jd_text="")                                  # 空串
import_jd(jd_text="随便写的文本")                       # 纯文本
import_jd(jd_text='{"raw_text":"只有这个字段"}')        # 缺业务字段
import_jd(jd_text='{"company":"某公司","role":"AI产品经理","requirements":["产品思维"]}')
```

**预期**：
- 前三个 → 结构化错误 `INVALID_JSON`（拒绝导入，不污染 target_jd）
- 最后一个 → `已导入目标 JD`

**验证点**：✅ 空串/纯文本/缺业务字段均被拒绝 ✅ 合法 JSON 正常导入

### 第 4 步：import_plan（导入既有规划）

**操作**（准备一个 md 规划文件）：
```
import_plan(file_path="C:/tmp/my_plan.md")
```

**预期**：返回文件内容解析 + 指引（整理为路线图结构后 save_roadmap）

**验证点**：✅ 解析正常 ✅ 指引去 save_roadmap

### 第 5 步：面经详情渲染（如抓过牛客）

**操作**（对话引导）：`fetch_company_jobs(company="nowcoder", params='{"keyword":"AI 产品"}')` → 取一个面经 URL → `fetch_jd_detail(url=...)`

**预期**：面经详情返回含 `### 面经内容`（正文渲染，不只是标题）

**验证点**：✅ 面经正文渲染（BUG-014 回归验证）

### 第 6 步：抓取失败诚实性

**操作**：用一个必然失败的方式抓取（如不合法的 company id）

**预期**：结构化错误 + 可用数据源列表 + 恢复建议（不编造数据）

**验证点**：✅ 失败时如实报错，绝不伪造岗位

---

## 5. 产出物验证清单

| 产出物 | 触发 | 验证 |
|--------|------|------|
| 欢迎手册 | `start_session` | 含流程与方法论 |
| 进度仪表盘 HTML | `export_dashboard(mode="progress")` | 双击可看：总进度/阶段进度/能力证据/调整历史 |
| 职业地图 HTML | `export_dashboard(mode="roadmap")` | 双击可看：完整路线图/占位徽标/起点层级/执行进度 |
| 日程表（可选） | 对话中让 AI 写 | AI 直接产出 markdown/HTML 文档，时间由用户填，系统不存储 |

---

## 6. 验证结果记录表

复制此表填写，验证完发我（含失败信息）。

```
## 场景 A：零基础全流程
- [ ] A1  start_session 欢迎手册 + 当前档案
- [ ] A2  intake who/have（零基础如实记录）
- [ ] A3  finalize_profile 目标缺失提醒
- [ ] A4  get_workflow_status 引导 explore_goals
- [ ] A5  analyze_gaps 无目标被拒
- [ ] A6  explore_goals 返回方法论
- [ ] A7  对话选方向（AI 抓真实数据 + Fit Filters + 不测评）
- [ ] A8  intake want 落定
- [ ] A9  explore_goals 已有目标守卫
- [ ] A10 analyze_gaps 放行（两个方法论）
- [ ] A11 list_data_sources / get_scraper_guide / fetch_company_jobs
- [ ] A12 save_gap_analysis 保存
- [ ] A13 generate_roadmap 方法论
- [ ] A14 save_roadmap（jd 三件套软校验 + HTML）
- [ ] A15 generate_tasks 生成任务
- [ ] A16 get_next_tasks（全流程概览）
- [ ] A17 checkin_task（能力证据沉淀）
- [ ] A18 trigger_insight（阶段审计）
- [ ] A19 apply_insight（调整落地）
- [ ] A20 get_progress + export_dashboard（progress/roadmap）

## 场景 B：多档案管理
- [ ] B1  list_profiles
- [ ] B2  switch_profile（不存在→错误；存在→切换）
- [ ] B3  数据隔离
- [ ] B4  delete_profile（需 confirm）
- [ ] B5  list_trash + restore_profile
- [ ] B6  恢复冲突拒绝
- [ ] B7  非法档案名守卫

## 场景 C：数据获取与守卫
- [ ] C1  list_data_sources + get_scraper_guide
- [ ] C2  search_knowledge（无结果诚实返回）
- [ ] C3  import_jd（非法拒绝/合法导入）
- [ ] C4  import_plan
- [ ] C5  fetch_jd_detail 面经正文
- [ ] C6  抓取失败诚实性
```

---

*生成于 2026-08-28 · 工具版本 30 个*