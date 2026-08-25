"""Career Kit MCP 服务器——入口。"""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .tools.errors import (
    AnalysisError,
    CareerKitError,
    InvalidJsonError,
    InvalidSectionError,
    MissingDataError,
    error_response,
)
from .tools.gap_analyzer import format_gap_report, parse_gap_analysis
from .tools.methodology import build_methodology_context
from .tools.market import (
    build_market_search_prompt,
    format_market_results,
    search_market_data,
)
from .tools.plan_importer import compare_plans, format_diff_report, parse_plan_file
from .tools.progress import (
    build_checkin_prompt,
    format_checkin_report,
    format_progress_overview,
    parse_checkin_response,
    save_checkin,
)
from .tools.roadmap import format_roadmap, parse_roadmap
from .tools.schedule import format_schedule, generate_ics, parse_schedule
from .tools.profile import (
    get_plan_history,
    load_profile,
    merge_section,
    restore_plan_version,
    save_plan_snapshot,
    save_profile,
)
from .models import JourneyEntry
from .tools.resume_parser import extract_text
from .tools.session import get_welcome_message
from .scrapers import list_scrapers, search_company_jobs, get_job_detail

mcp = FastMCP("career-kit")

# 文档根目录
DOCS_ROOT = Path(__file__).parent.parent / "docs"


# ============================================================
# MCP Resources - 文档资源
# ============================================================


@mcp.resource("career-kit://docs/llms")
def get_llms_doc() -> str:
    """LLM 使用指南：工作流、工具分类、常见场景"""
    return (DOCS_ROOT / "llms.txt").read_text(encoding="utf-8")


@mcp.resource("career-kit://docs/workflow")
def get_workflow_doc() -> str:
    """工作流详解：完整工作流、前置条件、输入输出"""
    return (DOCS_ROOT / "workflow.md").read_text(encoding="utf-8")


@mcp.resource("career-kit://docs/scrapers")
def get_scrapers_doc() -> str:
    """企业库总览：已收录企业、数据源说明"""
    return (DOCS_ROOT / "scrapers.md").read_text(encoding="utf-8")


@mcp.resource("career-kit://docs/scrapers/{scraper_id}")
def get_scraper_doc(scraper_id: str) -> str:
    """特定企业文档：BOSS直聘、字节跳动、牛客网"""
    path = DOCS_ROOT / "scrapers" / f"{scraper_id}.md"
    if not path.exists():
        return f"文档不存在：{scraper_id}"
    return path.read_text(encoding="utf-8")


@mcp.resource("career-kit://docs/tools")
def get_tools_doc() -> str:
    """工具总览：MCP 工具列表、分类说明"""
    return (DOCS_ROOT / "tools.md").read_text(encoding="utf-8")


@mcp.resource("career-kit://docs/knowledge")
def get_knowledge_doc() -> str:
    """知识库结构：目录结构、文件格式"""
    return (DOCS_ROOT / "knowledge.md").read_text(encoding="utf-8")


@mcp.resource("career-kit://docs/examples")
def get_examples_doc() -> str:
    """示例目录：完整工作流示例、场景示例"""
    return (DOCS_ROOT / "examples" / "README.md").read_text(encoding="utf-8")


def _parse_json_param(raw: str, field_name: str = "参数") -> dict:
    """解析 JSON 字符串参数，失败时抛出 InvalidJsonError。"""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise InvalidJsonError(
            f"{field_name} JSON 解析失败：{exc}",
            {"raw": raw[:200]},
        ) from exc
    if not isinstance(data, dict):
        raise InvalidJsonError(
            f"{field_name} 必须是 JSON 对象（dict），收到的是 {type(data).__name__}",
            {"raw": raw[:200]},
        )
    return data


@mcp.tool()
def start_session() -> str:
    """初始化新的职业规划会话。

    何时调用：用户开始新的职业规划时首先调用此工具。
    返回欢迎信息，引导用户开始建档流程。

    工作流程：start_session → intake(who) → intake(have) → intake(want) → finalize_profile
    """
    return (
        f"{get_welcome_message()}\n\n"
        "下一步：请调用 intake 工具填充档案信息。\n"
        '示例：intake(section="who", data=\'{"name":"张三", "education":"计算机本科"}\')'
    )


@mcp.tool()
def parse_resume(file_path: str) -> str:
    """解析简历文件，提取文本内容。支持 PDF、DOCX、Markdown、TXT 格式。

    Args:
        file_path: 简历文件的绝对路径
    """
    try:
        text = extract_text(file_path)
    except FileNotFoundError as e:
        return error_response("MISSING_DATA", str(e), {"file_path": file_path})
    except ValueError as e:
        return error_response("INVALID_JSON", str(e), {"file_path": file_path})

    return (
        f"--- RESUME CONTENT ---\n{text}\n--- END ---\n\n"
        "根据以上简历内容，请调用 intake 工具填充：\n"
        '- "who" section：姓名、联系方式、教育背景、当前状态\n'
        '- "have" section：技能、工作经历、项目经验、证书\n\n'
        '示例：intake(section="who", data=\'{"name":"张三", "education":"..."}\')'
    )


@mcp.tool()
def intake(section: str, data: str) -> str:
    """逐步填充档案信息。

    何时调用：在 start_session 之后，根据用户描述逐步填充档案。
    每次调用填充一个 section，可以多次调用。

    Args:
        section: 填充到哪个 section，可选 who / have / want / plan
            - who: 你是谁（姓名、教育、状态）
            - have: 你有什么（技能、经历、资源）
            - want: 你想要什么（目标岗位、行业、薪资）
            - plan: 计划（通常由 generate_roadmap 自动生成）
        data: 用户提供的信息，期望是 JSON 字符串
            示例：'{"name":"张三", "education":"计算机本科", "skills":["Python", "React"]}'
    """
    if section not in ("who", "have", "want", "plan"):
        return error_response(
            "INVALID_SECTION",
            f"section 必须是 who/have/want/plan，收到的是「{section}」",
            {"received": section, "valid": ["who", "have", "want", "plan"]},
        )

    profile = merge_section(section, data)
    return f"已记录到「{section}」。当前档案版本：v{profile.version}"


@mcp.tool()
def finalize_profile() -> str:
    """确认档案信息完整，生成摘要，解锁分析工具。

    何时调用：当用户已经通过 intake 填充了 who/have/want 三个 section 后调用。
    不要在档案不完整时调用此工具。

    前置条件：至少 who/have/want 中有一个 section 有内容。
    后续步骤：调用 analyze_gaps 开始差距分析。
    """
    profile = load_profile()

    # 生成简单的结构化摘要
    parts = []
    if profile.who:
        parts.append(f"身份：{_summarize_dict(profile.who)}")
    if profile.have:
        parts.append(f"现状：{_summarize_dict(profile.have)}")
    if profile.want:
        parts.append(f"目标：{_summarize_dict(profile.want)}")

    profile.summary = "；".join(parts) if parts else "（档案为空）"
    save_profile(profile)

    return (
        f"档案已确认。\n\n摘要：{profile.summary}\n\n"
        "可以开始分析差距了，请调用 analyze_gaps。"
    )


def _summarize_dict(d: dict) -> str:
    """将字典转为简洁的文本摘要。"""
    items = [f"{k}={v}" for k, v in d.items() if k != "raw"]
    if not items and "raw" in d:
        return str(d["raw"])
    return "，".join(items)


@mcp.tool()
def import_jd(jd_text: str) -> str:
    """导入目标岗位的 JD（职位描述）。

    Args:
        jd_text: JD 文本内容
    """
    # 将 JD 存储到 profile 的 target_jd 字段
    # LLM 应该先解析 JD 再调用此工具，所以这里直接存储
    profile = load_profile()

    # 如果 jd_text 是 JSON，直接存储；否则存为 raw
    try:
        jd_data = json.loads(jd_text)
        if not isinstance(jd_data, dict):
            jd_data = {"raw": jd_text}
    except json.JSONDecodeError:
        jd_data = {"raw": jd_text}

    profile.target_jd = jd_data
    profile.touch()
    save_profile(profile)

    return (
        f"已导入目标 JD。当前档案版本：v{profile.version}\n\n"
        "请调用 analyze_gaps 开始差距分析。"
    )


@mcp.tool()
def import_jd_file(file_path: str) -> str:
    """从文件导入目标岗位的 JD（职位描述）。支持 PDF、DOCX、Markdown、TXT 格式。

    Args:
        file_path: JD 文件的绝对路径
    """
    try:
        text = extract_text(file_path)
    except FileNotFoundError as e:
        return error_response("MISSING_DATA", str(e), {"file_path": file_path})
    except ValueError as e:
        return error_response("INVALID_JSON", str(e), {"file_path": file_path})

    return (
        f"--- JD CONTENT ---\n{text}\n--- END ---\n\n"
        "根据以上 JD 内容，请调用 import_jd 工具导入：\n"
        '示例：import_jd(jd_text=\'{"company":"字节跳动","role":"AI Agent 工程师","requirements":[...]}\'）'
    )


@mcp.tool()
def analyze_gaps() -> str:
    """对比现状（have）与目标（want/target_jd），输出差距分析。

    返回方法论上下文。LLM 按照方法论指引，使用 search_market 搜索补充数据，
    分析差距，然后调用 save_gap_analysis(gap_json) 保存结果。

    前置条件：档案已通过 finalize_profile 确认。
    后续步骤：LLM 分析后调用 save_gap_analysis，然后调用 generate_roadmap。
    """
    profile = load_profile()

    if not profile.have and not profile.want:
        return error_response(
            "MISSING_DATA",
            "档案中缺少 have（现状）或 want（目标）信息。请先调用 intake 填充。",
            {"missing": ["have", "want"]},
        )

    # 加载两个方法论
    ctx1 = build_methodology_context("resume_screening", profile)
    ctx2 = build_methodology_context("interview_prep", profile)

    # 记录到 journey
    profile.append_journey(JourneyEntry(
        phase="analysis",
        decision="启动差距分析",
    ))
    save_profile(profile)

    return {
        "methodologies": [ctx1["methodology"], ctx2["methodology"]],
        "profile": ctx1["profile"],
        "existing_journey": [
            {"phase": j.phase, "decision": j.decision, "timestamp": j.timestamp}
            for j in (profile.journey or [])[-5:]
        ],
        "instructions": (
            "请按照上述方法论指引：\n"
            "1. 先用 search_market 搜索目标岗位的真实 JD 和同背景案例\n"
            "2. 基于数据从简历过筛和面试通过两个维度分析差距\n"
            "3. 调用 save_gap_analysis(gap_json) 保存结构化结果"
        ),
    }


@mcp.tool()
def save_gap_analysis(gap_json: str) -> str:
    """保存差距分析结果。

    何时调用：在 analyze_gaps 返回分析任务，LLM 完成分析后调用此工具保存结果。

    Args:
        gap_json: 差距分析的 JSON 字符串

    Schema:
        {
            "match_score": 65,           // 匹配度评分（0-100）
            "skill_gaps": [              // 技能差距列表
                {
                    "skill": "TypeScript",      // 技能名称
                    "priority": "high",         // 优先级：high/medium/low
                    "current_level": "无",      // 当前水平
                    "target_level": "熟练",     // 目标水平
                    "source": "BOSS直聘 JD"     // 数据来源
                }
            ],
            "priority_actions": [        // 优先行动项
                "学习 TypeScript 基础",
                "完成 TypeScript 项目"
            ],
            "strengths": [               // 优势
                "有前端开发经验"
            ]
        }
    """
    try:
        gap_data = _parse_json_param(gap_json, "差距分析")
    except InvalidJsonError as exc:
        return error_response(exc.code, exc.message, exc.details)

    profile = load_profile()
    profile.gap = gap_data
    profile.touch()
    save_profile(profile)

    # 记录到 journey
    profile.append_journey(JourneyEntry(
        phase="analysis",
        analysis={"match_score": gap_data.get("match_score"), "gaps_count": len(gap_data.get("skill_gaps", []))},
        decision="用户确认差距分析",
    ))
    save_profile(profile)

    # 格式化报告
    report = format_gap_report(gap_data)

    return {
        "message": (
            f"差距分析已保存。\n\n{report}\n\n"
            "接下来可以调用 generate_roadmap 生成路线图。"
        ),
        "next_steps": ["generate_roadmap"],
        "context": {
            "phase": "gap_saved",
            "match_score": gap_data.get("match_score"),
            "gaps_count": len(gap_data.get("skill_gaps", [])),
        },
    }


@mcp.tool()
def generate_roadmap() -> str:
    """基于差距分析生成分阶段职业路线图。

    返回方法论上下文。LLM 按照方法论指引，结合差距分析结果，
    设计分阶段路线图，然后调用 save_roadmap(roadmap_json) 保存。

    前置条件：差距分析已完成（save_gap_analysis 已调用）。
    后续步骤：LLM 生成路线图后调用 save_roadmap，然后调用 generate_schedule。
    """
    profile = load_profile()

    if not profile.gap:
        return error_response(
            "MISSING_DATA",
            "请先调用 analyze_gaps 完成差距分析，再生成路线图。",
            {"missing": "gap"},
        )

    ctx = build_methodology_context("roadmap", profile)

    return {
        "methodology": ctx["methodology"],
        "profile": ctx["profile"],
        "instructions": (
            "请按照路线图方法论指引：\n"
            "1. 先用 search_market 搜索目标岗位的真实技能要求\n"
            "2. 基于差距分析和市场数据，设计分阶段路线图\n"
            "3. 调用 save_roadmap(roadmap_json) 保存结构化结果"
        ),
    }


@mcp.tool()
def save_roadmap(roadmap_json: str) -> str:
    """保存路线图到档案。

    Args:
        roadmap_json: 路线图的 JSON 字符串

    Schema:
        {
            "phases": [                  // 阶段列表
                {
                    "name": "基础学习",           // 阶段名称
                    "duration": "2周",            // 阶段时长
                    "description": "学习基础",    // 阶段描述
                    "milestones": [               // 里程碑列表
                        {
                            "name": "Python 基础",        // 里程碑名称
                            "duration": "3天",            // 里程碑时长
                            "description": "学习 Python", // 里程碑描述
                            "tasks": [                    // 任务列表
                                {
                                    "name": "学习装饰器",           // 任务名称
                                    "estimated_days": 1,           // 预计天数
                                    "priority": "high"             // 优先级
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    """
    try:
        roadmap_data = _parse_json_param(roadmap_json, "路线图")
    except InvalidJsonError as exc:
        return error_response(exc.code, exc.message, exc.details)

    profile = load_profile()

    # 保存旧版本快照
    if profile.plan:
        save_plan_snapshot(source="before_roadmap")

    # 解析并写入 plan
    parsed = parse_roadmap(json.dumps(roadmap_data, ensure_ascii=False))
    profile.plan = parsed
    profile.touch()
    save_profile(profile)

    # 保存新版本快照
    save_plan_snapshot(source="roadmap_generated")

    # 格式化报告
    report = format_roadmap(parsed)

    return {
        "message": (
            f"路线图已保存。\n\n{report}\n\n"
            "接下来可以调用 generate_schedule 获取具体日程。"
        ),
        "next_steps": ["generate_schedule"],
        "context": {"phase": "roadmap_saved", "version": profile.version},
    }


@mcp.tool()
def generate_schedule(scope: str = "this_week") -> str:
    """将路线图拆解为每日时间块日程表。

    返回方法论上下文。LLM 按照方法论指引，将路线图任务分配到日程中，
    然后调用 save_schedule(schedule_json) 保存。

    Args:
        scope: 范围，可选 today / this_week / this_month

    前置条件：路线图已完成（save_roadmap 已调用）。
    后续步骤：LLM 生成日程后调用 save_schedule，然后调用 export_ics 导出日历。
    """
    profile = load_profile()

    if not profile.plan or not profile.plan.get("roadmap"):
        return error_response(
            "MISSING_DATA",
            "请先调用 generate_roadmap 生成路线图，再生成日程。",
            {"missing": "roadmap"},
        )

    ctx = build_methodology_context("schedule", profile)
    ctx["profile"]["scope"] = scope

    # 估算可用时间
    from .tools.schedule import _estimate_available_time
    available_time = _estimate_available_time(profile)
    ctx["profile"]["available_time"] = available_time

    return {
        "methodology": ctx["methodology"],
        "profile": ctx["profile"],
        "instructions": (
            f"范围：{scope}\n"
            "请按照日程方法论指引：\n"
            "1. 从路线图中提取当前范围内的任务\n"
            "2. 按优先级和依赖关系分配到每日时间块\n"
            "3. 调用 save_schedule(schedule_json) 保存结构化结果"
        ),
    }


@mcp.tool()
def save_schedule(schedule_json: str) -> str:
    """保存日程表到档案。

    Args:
        schedule_json: 日程表的 JSON 字符串

    Schema:
        {
            "schedule": [                // 日程列表
                {
                    "date": "2026-08-26",         // 日期
                    "tasks": [                    // 任务列表
                        {
                            "name": "学习 Python",        // 任务名称
                            "start_time": "09:00",        // 开始时间
                            "end_time": "11:00",          // 结束时间
                            "duration_hours": 2,          // 时长（小时）
                            "priority": "high"            // 优先级
                        }
                    ]
                }
            ]
        }
    """
    try:
        schedule_data = _parse_json_param(schedule_json, "日程表")
    except InvalidJsonError as exc:
        return error_response(exc.code, exc.message, exc.details)

    profile = load_profile()

    # 解析并写入 plan
    parsed = parse_schedule(json.dumps(schedule_data, ensure_ascii=False))
    profile.plan["schedule"] = parsed.get("schedule", parsed)
    profile.touch()
    save_profile(profile)

    # 格式化报告
    report = format_schedule(parsed)

    return {
        "message": (
            f"日程表已保存。\n\n{report}\n\n"
            "如需导出 ICS 日历文件，请调用 export_ics。\n"
            "开始执行后，请调用 track_progress 记录进度。"
        ),
        "next_steps": ["export_ics", "track_progress"],
        "context": {"phase": "schedule_saved", "version": profile.version},
    }


@mcp.tool()
def export_ics(start_date: str = "") -> str:
    """导出日程为 ICS 日历文件。

    Args:
        start_date: 起始日期（YYYY-MM-DD），为空则从今天开始
    """
    import tempfile
    from pathlib import Path

    profile = load_profile()

    schedule = profile.plan.get("schedule")
    if not schedule:
        return error_response(
            "MISSING_DATA",
            "请先调用 generate_schedule 生成日程。",
            {"missing": "schedule"},
        )

    # 生成 ICS
    ics_content = generate_ics({"schedule": schedule}, start_date)

    # 写入临时文件
    ics_path = Path(tempfile.gettempdir()) / "career_kit_schedule.ics"
    ics_path.write_text(ics_content, encoding="utf-8")

    return (
        f"ICS 文件已生成：{ics_path}\n\n"
        "可以导入到 Google Calendar / Outlook / Apple Calendar 等日历应用。\n"
        "开始执行后，请调用 track_progress 记录进度。"
    )


@mcp.tool()
def track_progress(report: str) -> str:
    """记录进度签到，分析偏差，自动调整后续计划。

    何时调用：用户汇报学习/工作进度时调用。例如：
    - "今天把 React 教程刷完了"
    - "TypeScript 学了一周，感觉进度太慢"
    - "面试挂了，需要调整计划"

    签到模式：
    - 完成了什么任务
    - 花了多少时间
    - 遇到什么阻碍
    - 当前士气

    工作流程：
    1. 用户汇报进度（自然语言）
    2. LLM 分析进度，调用 save_checkin 保存
    3. 如果需要调整计划，调用 generate_schedule 重新生成日程

    Args:
        report: 用户的进度汇报（自然语言）
            示例："今天把 React 教程刷完了，花了 3 小时"
    """
    profile = load_profile()

    if not profile.plan:
        return error_response(
            "MISSING_DATA",
            "请先生成路线图和日程。",
            {"missing": "plan"},
        )

    # 构建签到分析 prompt
    prompt = build_checkin_prompt(profile, report)

    return (
        f"【进度签到任务】\n\n"
        f"{'=' * 50}\n\n"
        f"{prompt}\n\n"
        f"{'=' * 50}\n\n"
        "请分析用户的进度汇报，然后调用 save_checkin(checkin_json) 保存结果。"
    )


@mcp.tool()
def save_checkin(checkin_json: str) -> str:
    """保存签到记录。

    Args:
        checkin_json: 签到分析的 JSON 字符串
    """
    try:
        checkin_data = _parse_json_param(checkin_json, "签到数据")
    except InvalidJsonError as exc:
        return error_response(exc.code, exc.message, exc.details)

    profile = load_profile()
    profile = save_checkin(profile, checkin_data)
    save_profile(profile)

    # 格式化报告
    report = format_checkin_report(checkin_data)

    # 如果需要调整计划
    adjustments = checkin_data.get("adjustments", {})
    if adjustments.get("needed"):
        report += "\n\n⚠️ 检测到计划需要调整。建议调用 generate_schedule 重新生成日程。"

    return (
        f"签到已保存。\n\n{report}\n\n"
        "继续加油！下次签到请调用 track_progress。"
    )


@mcp.tool()
def view_progress() -> str:
    """查看整体进度概览。"""
    profile = load_profile()

    if not profile.plan:
        return "暂无计划，请先生成路线图。"

    return format_progress_overview(profile)


@mcp.tool()
def search_market(query: str) -> str:
    """搜索就业市场信息。

    何时调用：用户询问市场相关信息时调用。例如：
    - "字节跳动前端薪资多少？"
    - "AI Agent 工程师面试问什么？"
    - "React 和 Vue 哪个更好找工作？"

    搜索类型自动推断：
    - 面试相关 → 搜索面经
    - 薪资相关 → 搜索薪资数据
    - JD 相关 → 搜索岗位要求
    - 其他 → 市场趋势

    数据来源（按优先级）：
    1. 本地知识库（dev/knowledge/market/）
    2. LLM 知识（兜底）

    Args:
        query: 搜索内容——岗位名称、公司、薪资、面试经验等
            示例："字节跳动前端开发 面经"
    """
    # 搜索数据
    search_results = search_market_data(query)

    # 构建 LLM prompt
    prompt = build_market_search_prompt(query, search_results)

    # 数据来源提示
    source_info = ""
    if search_results["has_local_data"]:
        source_info = "（已找到本地参考数据）"
    else:
        source_info = "（基于 LLM 知识回答）"

    return (
        f"【市场搜索】{query} {source_info}\n\n"
        f"{prompt}\n\n"
        "请基于以上信息回答用户的问题。"
    )


@mcp.tool()
def import_plan(file_path: str) -> str:
    """导入已有的职业规划文档。

    支持 PDF、DOCX、Markdown、TXT 格式。
    如果已有计划，会对比分析并询问保留哪些内容。

    Args:
        file_path: 计划文件的绝对路径
    """
    # 解析计划文件
    try:
        new_plan_text = parse_plan_file(file_path)
    except FileNotFoundError as e:
        return error_response("MISSING_DATA", str(e), {"file_path": file_path})
    except ValueError as e:
        return error_response("INVALID_JSON", str(e), {"file_path": file_path})

    profile = load_profile()

    # 如果没有旧计划，直接提示 LLM 填充
    if not profile.plan:
        return (
            f"--- PLAN CONTENT ---\n{new_plan_text}\n--- END ---\n\n"
            "这是新导入的计划文档。请根据内容调用 intake 工具填充 plan section：\n"
            '示例：intake(section="plan", data=\'{"phases": [...], "timeline": "..."}\')\n\n'
            "填充后请调用 save_plan_snapshot(source='imported', import_file='" + file_path + "') 保存版本快照。"
        )

    # 有旧计划时，需要 LLM 先解析新计划再对比
    return (
        f"--- NEW PLAN CONTENT ---\n{new_plan_text}\n--- END ---\n\n"
        "检测到已有计划档案。请按以下步骤操作：\n\n"
        "1. 将以上内容解析为结构化 JSON\n"
        "2. 调用 compare_plan_versions(new_plan_json) 对比新旧计划\n"
        "3. 根据对比结果询问用户保留哪些内容\n\n"
        "用户可选择：\n"
        "  A. 完全替换为新计划\n"
        "  B. 合并新旧计划\n"
        "  C. 保留旧计划，放弃导入"
    )


@mcp.tool()
def compare_plan_versions(new_plan: str) -> str:
    """对比新旧计划版本，显示差异。

    Args:
        new_plan: 新计划的 JSON 字符串
    """
    profile = load_profile()

    if not profile.plan:
        return error_response(
            "MISSING_DATA",
            "当前没有已有计划，无需对比。请直接调用 intake 填充 plan section。",
            {"missing": "plan"},
        )

    try:
        new_plan_dict = _parse_json_param(new_plan, "新计划")
    except InvalidJsonError as exc:
        return error_response(exc.code, exc.message, exc.details)

    diff = compare_plans(profile.plan, new_plan_dict)
    report = format_diff_report(diff)

    return (
        f"【新旧计划对比报告】\n\n{report}\n\n"
        "请选择操作：\n"
        '  A. 完全替换 — 调用 replace_plan(new_plan_json)\n'
        '  B. 合并计划 — 调用 merge_plan(new_plan_json)\n'
        "  C. 保留旧版 — 不做任何操作"
    )


@mcp.tool()
def replace_plan(new_plan: str) -> str:
    """用新计划完全替换旧计划。

    Args:
        new_plan: 新计划的 JSON 字符串
    """
    try:
        _parse_json_param(new_plan, "新计划")
    except InvalidJsonError as exc:
        return error_response(exc.code, exc.message, exc.details)

    # 保存旧版本快照
    save_plan_snapshot(source="replaced")

    # 替换计划
    profile = merge_section("plan", new_plan)

    # 保存新版本快照
    save_plan_snapshot(source="imported")

    return f"计划已完全替换。已保存版本历史，可随时回溯。当前版本：v{profile.version}"


@mcp.tool()
def merge_plan(new_plan: str) -> str:
    """合并新计划到已有计划。

    Args:
        new_plan: 新计划的 JSON 字符串（将深度合并到现有计划）
    """
    try:
        _parse_json_param(new_plan, "新计划")
    except InvalidJsonError as exc:
        return error_response(exc.code, exc.message, exc.details)

    # 保存旧版本快照
    save_plan_snapshot(source="before_merge")

    # 合并计划
    profile = merge_section("plan", new_plan)

    # 保存合并后版本快照
    save_plan_snapshot(source="merged")

    return f"计划已合并完成。已保存版本历史。当前版本：v{profile.version}"


@mcp.tool()
def list_plan_versions() -> str:
    """查看计划版本历史列表。"""
    history = get_plan_history()

    if not history:
        return "暂无计划版本历史。"

    lines = ["【计划版本历史】\n"]
    for v in history:
        lines.append(
            f"  v{v['version']} | {v['timestamp']} | 来源: {v['source']}"
            + (f" | 文件: {v['import_file']}" if v['import_file'] else "")
        )
        lines.append(f"    摘要: {v['summary']}")
        lines.append("")

    lines.append("如需恢复到某个版本，请调用 restore_plan(version=N)")
    return "\n".join(lines)


@mcp.tool()
def restore_plan(version: int) -> str:
    """恢复计划到指定版本。

    Args:
        version: 要恢复的版本号
    """
    try:
        # 先保存当前版本快照
        save_plan_snapshot(source="before_restore")

        # 恢复到指定版本
        profile = restore_plan_version(version)

        # 保存恢复后的版本快照
        save_plan_snapshot(source="restored")

        return f"已恢复到版本 v{version}。当前档案版本：v{profile.version}"
    except ValueError as e:
        return error_response("MISSING_DATA", str(e), {"version": version})


@mcp.tool()
def list_company_jobs() -> str:
    """列出所有已注册的企业招聘数据源。

    返回每个企业支持的搜索参数，方便后续调用 fetch_company_jobs。
    """
    scrapers = list_scrapers()

    if not scrapers:
        return "暂无已注册的企业数据源。社区贡献请参考 scrapers/ 目录。"

    lines = ["【已注册企业招聘数据源】\n"]
    for s in scrapers:
        lines.append(f"**{s['name']}**（ID: {s['id']}）")
        if s.get("description"):
            lines.append(f"  {s['description']}")

        params = s.get("params", {})
        if params:
            lines.append("  支持的搜索参数：")
            for pname, pinfo in params.items():
                req = "（必填）" if pinfo.get("required") else "（可选）"
                desc = pinfo.get("description", "")
                lines.append(f"    - {pname}{req}: {desc}")
        lines.append("")

    lines.append("调用示例：fetch_company_jobs(company=\"bytedance\", params='{\"keyword\":\"AI Agent\"}')")
    return "\n".join(lines)


@mcp.tool()
def fetch_company_jobs(company: str, params: str = "{}") -> str:
    """搜索指定企业的岗位。

    何时调用：用户想查看某个企业的招聘信息时调用。
    先调用 list_company_jobs 查看可用企业和支持的参数。

    Args:
        company: 企业 ID（通过 list_company_jobs 获取）
            示例：bytedance
        params: 搜索参数 JSON 字符串（各企业支持的参数不同）
            示例：'{"keyword":"AI Agent", "city":"北京"}'
    """
    try:
        params_dict = json.loads(params) if params else {}
    except (json.JSONDecodeError, TypeError) as exc:
        return error_response(
            "INVALID_JSON",
            f"params JSON 解析失败：{exc}",
            {"raw": params[:200]},
        )

    result = search_company_jobs(company, **params_dict)

    if result.get("error"):
        return error_response(
            "ANALYSIS_FAILED",
            result["error"],
            {"available": result.get("available", [])},
        )

    count = result["count"]
    company_name = result["company"]

    if count == 0:
        return f"「{company_name}」未找到匹配的岗位。"

    lines = [f"【{company_name}】找到 {count} 个岗位：\n"]
    for i, job in enumerate(result["results"], 1):
        title = job.get("title", "未知岗位")
        location = job.get("location", "")
        url = job.get("url", "")
        summary = job.get("summary", "")

        loc_str = f" | {location}" if location else ""
        lines.append(f"{i}. **{title}**{loc_str}")
        if url:
            lines.append(f"   链接：{url}")
        if summary:
            lines.append(f"   {summary[:100]}")
        lines.append("")

    lines.append("获取岗位详情：fetch_jd_detail(url=\"具体岗位URL\")")
    return "\n".join(lines)


@mcp.tool()
def fetch_jd_detail(url: str, company: str = "") -> str:
    """获取岗位详情（JD 全文）。

    Args:
        url: 岗位详情页 URL
        company: 企业 ID（可选，不填则自动尝试所有已注册的 Scraper）
    """
    result = get_job_detail(url, company if company else None)

    if result.get("error"):
        return error_response("ANALYSIS_FAILED", result["error"], {"url": url})

    lines = [f"## {result.get('title', '岗位详情')}"]
    if result.get("company"):
        lines.append(f"**公司**：{result['company']}")
    if result.get("location"):
        lines.append(f"**地点**：{result['location']}")
    if result.get("salary"):
        lines.append(f"**薪资**：{result['salary']}")
    lines.append("")

    if result.get("description"):
        lines.append("### 岗位描述")
        lines.append(result["description"])
        lines.append("")

    if result.get("requirements"):
        lines.append("### 任职要求")
        lines.append(result["requirements"])
        lines.append("")

    if result.get("benefits"):
        lines.append("### 福利待遇")
        lines.append(result["benefits"])
        lines.append("")

    lines.append("如需导入此 JD 进行差距分析，请调用 import_jd(jd_text=...)。")
    return "\n".join(lines)


# ============================================================
# Phase 2: 任务管理 Tools
# ============================================================


@mcp.tool()
def generate_tasks() -> str:
    """从路线图生成任务列表。

    何时调用：在 generate_roadmap 和 generate_schedule 之后调用，将路线图转化为可执行的任务。
    前置条件：档案中已有路线图（plan.roadmap）。
    后续步骤：调用 get_today_tasks 获取今日任务。
    """
    from .tools.task_manager import (
        create_tasks_from_roadmap,
        format_task_list,
        set_deadlines,
    )

    profile = load_profile()

    if not profile.plan.get("roadmap") and not profile.plan.get("phases"):
        return error_response(
            "MISSING_DATA",
            "档案中没有路线图，请先调用 generate_roadmap。",
            {"section": "plan"},
        )

    # 清空旧任务
    profile.tasks = []

    # 从路线图生成任务
    tasks = create_tasks_from_roadmap(profile)

    # 设置截止日期
    tasks = set_deadlines(tasks)

    # 添加到档案
    for task in tasks:
        profile.add_task(task)

    save_profile(profile)

    return {
        "message": f"已从路线图生成 {len(tasks)} 个任务。",
        "tasks": format_task_list(tasks, "生成的任务"),
        "next_steps": ["get_today_tasks"],
        "context": {"phase": "tasks_generated", "task_count": len(tasks)},
    }


@mcp.tool()
def get_today_tasks() -> str:
    """获取今日待办任务。

    何时调用：用户想查看今天需要做什么时调用。
    返回待办任务列表，包括进行中和待办的任务。
    """
    from .tools.task_manager import format_task_list, format_progress_overview

    profile = load_profile()

    if not profile.tasks:
        return {
            "message": "暂无任务。请先调用 generate_tasks 从路线图生成任务。",
            "next_steps": ["generate_tasks"],
            "context": {"phase": "no_tasks"},
        }

    today_tasks = profile.get_today_tasks()
    overdue_tasks = profile.get_overdue_tasks()

    lines = []

    if overdue_tasks:
        lines.append(format_task_list(overdue_tasks, "⚠️ 超期任务"))
        lines.append("")

    lines.append(format_task_list(today_tasks, "📋 今日任务"))
    lines.append("")
    lines.append(format_progress_overview(profile))

    # 打卡提示
    if today_tasks:
        lines.append("---")
        lines.append("完成任务后，请调用 checkin_task 打卡。")
        lines.append(f"示例：checkin_task(task_id=\"{today_tasks[0].id}\")")

    return "\n".join(lines)


@mcp.tool()
def checkin_task(task_id: str, status: str = "completed", notes: str = "") -> str:
    """打卡任务。

    何时调用：用户完成或跳过某个任务时调用。
    会自动检查超期情况并触发洞察。

    Args:
        task_id: 任务 ID（从 get_today_tasks 获取）
        status: 打卡状态（completed 或 skipped）
        notes: 备注（可选）
    """
    from .tools.task_manager import (
        add_depth_tasks,
        check_overdue_tasks,
        checkin_task as do_checkin,
        compress_schedule,
        format_progress_overview,
    )
    from .tools.insight import check_stage_completion

    profile = load_profile()

    try:
        profile, checkin = do_checkin(profile, task_id, status, notes)
    except ValueError as e:
        return error_response("MISSING_DATA", str(e), {"task_id": task_id})

    # 检查是否有超期任务
    overdue_tasks = check_overdue_tasks(profile)

    # 检查阶段是否完成
    stage_completed = check_stage_completion(profile)

    lines = []
    task = profile.get_task(task_id)
    lines.append(f"✅ 已打卡：{task.name if task else task_id}")
    lines.append("")

    # 超期提醒
    if overdue_tasks:
        lines.append(f"⚠️ 有 {len(overdue_tasks)} 个任务超期：")
        for t in overdue_tasks:
            lines.append(f"- {t.name}（超期 {t.days_overdue():.1f} 天）")
        lines.append("")
        lines.append("建议调用 trigger_insight 检查是否需要调整计划。")

    # 阶段完成提醒
    if stage_completed:
        lines.append("")
        lines.append("🎯 恭喜！你已完成一个阶段。建议调用 trigger_insight 进行阶段审计。")

    # 提前完成 - 添加深度任务
    if status == "completed" and task and not task.is_overdue():
        depth_tasks = add_depth_tasks(profile, task_id)
        if depth_tasks:
            lines.append("")
            lines.append(f"💡 提前完成！已添加深度任务：{depth_tasks[0].name}")

    save_profile(profile)

    lines.append("")
    lines.append(format_progress_overview(profile))

    return "\n".join(lines)


@mcp.tool()
def trigger_insight(trigger_type: str = "proactive", event_description: str = "") -> str:
    """触发洞察检查。

    何时调用：
    - 用户完成阶段后（trigger_type="stage_audit"）
    - 用户报告事件时（trigger_type="event"）
    - 定期检查进度时（trigger_type="proactive"）

    工作流程：
    1. 调用 trigger_insight 获取分析 prompt
    2. LLM 根据 prompt 分析用户进度
    3. LLM 生成洞察 JSON
    4. 调用 apply_insight(insight_json) 应用结果

    Args:
        trigger_type: 触发类型（stage_audit, event, proactive）
        event_description: 事件描述（当 trigger_type 为 event 时必填）

    Returns:
        包含分析 prompt 和使用说明的字典
    """
    from .tools.insight import build_insight_prompt

    profile = load_profile()

    if not profile.tasks:
        return {
            "message": "暂无任务，请先调用 generate_tasks。",
            "next_steps": ["generate_tasks"],
            "context": {"phase": "no_tasks"},
        }

    # 构建 prompt
    prompt = build_insight_prompt(profile, trigger_type, event_description)

    return {
        "message": "洞察分析任务已准备。请根据以下 prompt 进行分析，然后调用 apply_insight 应用结果。",
        "prompt": prompt,
        "output_format": {
            "status": "on_track|behind|ahead|need_adjustment",
            "summary": "进度总结",
            "insights": ["洞察1", "洞察2"],
            "adjustment_needed": True,
            "adjustment_reason": "调整原因",
            "changes": [{"type": "compress_task|add_task", "task_id": "task_001", "details": {}}],
            "user_message": "给用户的消息"
        },
        "next_steps": ["apply_insight"],
        "context": {"phase": "insight_ready", "trigger_type": trigger_type},
    }


@mcp.tool()
def apply_insight(insight_json: str) -> str:
    """应用洞察分析结果到档案。

    何时调用：在 trigger_insight 之后，LLM 分析完成后调用。

    Args:
        insight_json: LLM 返回的洞察分析 JSON

    Schema:
        {
            "status": "on_track",        // 状态：on_track/behind/ahead/need_adjustment
            "summary": "进度正常",        // 进度总结
            "insights": [                // 洞察列表
                "学习速度超预期",
                "可以加深难度"
            ],
            "adjustment_needed": false,  // 是否需要调整
            "adjustment_type": "auto",   // 调整类型：auto/manual
            "adjustment_reason": "",     // 调整原因
            "changes": [                 // 调整列表
                {
                    "type": "compress_task",  // 类型：compress_task/add_task/remove_task
                    "task_id": "task_001",    // 任务 ID
                    "details": {              // 详情
                        "new_days": 2
                    }
                }
            ],
            "user_message": "给用户的消息"
        }
    """
    from .tools.insight import (
        apply_adjustment,
        format_insight_report,
        parse_insight_response,
    )

    profile = load_profile()

    try:
        insight_result = json.loads(insight_json)
    except json.JSONDecodeError as e:
        return error_response("INVALID_JSON", f"洞察 JSON 解析失败：{e}", {"raw": insight_json[:200]})

    # 应用调整
    if insight_result.get("adjustment_needed"):
        profile, adjustment = apply_adjustment(profile, insight_result)
        save_profile(profile)

        return {
            "message": "已应用调整。",
            "report": format_insight_report(insight_result),
            "adjustment": adjustment.model_dump(),
            "context": {"phase": "adjustment_applied"},
        }
    else:
        return {
            "message": "无需调整。",
            "report": format_insight_report(insight_result),
            "context": {"phase": "insight_complete"},
        }


@mcp.tool()
def get_progress() -> str:
    """获取进度概览。

    何时调用：用户想查看整体进度时调用。
    返回任务统计、打卡记录、调整历史。
    """
    from .tools.task_manager import format_progress_overview

    profile = load_profile()

    if not profile.tasks:
        return {
            "message": "暂无任务。请先调用 generate_tasks 从路线图生成任务。",
            "next_steps": ["generate_tasks"],
            "context": {"phase": "no_tasks"},
        }

    lines = []
    lines.append(format_progress_overview(profile))

    # 调整历史
    if profile.adjustments:
        lines.append("## 📝 调整历史")
        for adj in profile.adjustments[-5:]:
            lines.append(f"- {adj.timestamp[:10]}：{adj.reason}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def suggest_adjustment() -> str:
    """AI 提出调整建议。

    何时调用：用户想让 AI 检查进度并提出调整建议时调用。
    返回调整建议，用户确认后可调用 apply_adjustment 应用。
    """
    from .tools.task_manager import check_overdue_tasks, compress_schedule

    profile = load_profile()

    if not profile.tasks:
        return {
            "message": "暂无任务，请先调用 generate_tasks。",
            "next_steps": ["generate_tasks"],
            "context": {"phase": "no_tasks"},
        }

    # 检查超期任务
    overdue_tasks = check_overdue_tasks(profile)

    if not overdue_tasks:
        return {
            "message": "所有任务都在计划内，无需调整。",
            "context": {"phase": "no_adjustment_needed"},
        }

    # 计算超期天数
    total_overdue = sum(t.days_overdue() for t in overdue_tasks)

    # 压缩后续任务
    changes = compress_schedule(profile, total_overdue)

    # 保存调整记录
    adjustment = Adjustment(
        trigger=f"{len(overdue_tasks)} 个任务超期",
        trigger_type="proactive",
        reason=f"超期 {total_overdue:.1f} 天，压缩后续任务",
        changes=changes,
        approved=True,
    )
    profile.add_adjustment(adjustment)
    save_profile(profile)

    lines = []
    lines.append("## 🔄 调整建议")
    lines.append("")
    lines.append(f"发现 {len(overdue_tasks)} 个超期任务，共超期 {total_overdue:.1f} 天。")
    lines.append("")
    lines.append("### 调整方案")
    for change in changes:
        lines.append(f"- {change['task_name']}：{change['old_days']}天 → {change['new_days']}天")
    lines.append("")
    lines.append("已自动应用调整。")

    return "\n".join(lines)


@mcp.tool()
def get_workflow_status() -> str:
    """获取当前工作流状态和下一步建议。

    何时调用：
    - 用户开始对话时，了解当前进度
    - LLM 不确定下一步该做什么时
    - 需要查看整体状态时

    Returns:
        包含当前阶段、已完成步骤、下一步建议的字典
    """
    profile = load_profile()

    # 确定当前阶段
    phase = "not_started"
    completed_steps = []
    next_step = "start_session"

    if profile.who or profile.have or profile.want:
        phase = "profile_building"
        completed_steps.append("start_session")

        if profile.who:
            completed_steps.append("intake(who)")
        if profile.have:
            completed_steps.append("intake(have)")
        if profile.want:
            completed_steps.append("intake(want)")

        if not profile.summary:
            next_step = "finalize_profile"
        else:
            completed_steps.append("finalize_profile")

    if profile.summary:
        phase = "analysis"
        if not profile.gap:
            next_step = "analyze_gaps"
        else:
            completed_steps.append("analyze_gaps")

    if profile.gap:
        phase = "planning"
        if not profile.plan.get("roadmap"):
            next_step = "generate_roadmap"
        else:
            completed_steps.append("generate_roadmap")

    if profile.plan.get("roadmap"):
        phase = "scheduling"
        if not profile.plan.get("schedule"):
            next_step = "generate_schedule"
        else:
            completed_steps.append("generate_schedule")

    if profile.plan.get("schedule"):
        phase = "task_management"
        if not profile.tasks:
            next_step = "generate_tasks"
        else:
            completed_steps.append("generate_tasks")

    if profile.tasks:
        phase = "execution"
        completed_tasks = [t for t in profile.tasks if t.status == "completed"]
        overdue_tasks = [t for t in profile.tasks if t.is_overdue()]

        if overdue_tasks:
            next_step = "trigger_insight(proactive)"
        elif len(completed_tasks) == len(profile.tasks):
            phase = "completed"
            next_step = "目标达成！"
        else:
            next_step = "get_today_tasks"

    # 构建状态报告
    total_tasks = len(profile.tasks)
    completed_tasks = len([t for t in profile.tasks if t.status == "completed"])
    overdue_tasks = len([t for t in profile.tasks if t.is_overdue()])

    lines = []
    lines.append(f"## 当前状态：{phase}")
    lines.append("")
    lines.append(f"**下一步**：{next_step}")
    lines.append("")
    lines.append("### 已完成步骤")
    for step in completed_steps:
        lines.append(f"- ✅ {step}")
    lines.append("")
    lines.append("### 任务统计")
    lines.append(f"- 总计：{total_tasks} 个")
    lines.append(f"- 已完成：{completed_tasks} 个")
    if overdue_tasks > 0:
        lines.append(f"- 超期：{overdue_tasks} 个")
    lines.append("")
    lines.append("### 工作流指南")
    lines.append("- 建档：start_session → intake(who/have/want) → finalize_profile")
    lines.append("- 分析：analyze_gaps → save_gap_analysis")
    lines.append("- 规划：generate_roadmap → save_roadmap")
    lines.append("- 日程：generate_schedule → save_schedule")
    lines.append("- 任务：generate_tasks → get_today_tasks")
    lines.append("- 执行：checkin_task → trigger_insight → apply_insight")

    return "\n".join(lines)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
