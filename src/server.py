"""Career Kit MCP 服务器——入口。"""

import asyncio
import json
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

# 抑制 pydantic_settings 对 mcp 内部 Settings 模型的误报告警（OBS-002）
# 该告警来自 FastMCP 内部 lifespan 字段的前向引用，不影响功能
try:
    from pydantic_settings.exceptions import IncompleteFieldDefinitionWarning
    warnings.filterwarnings("ignore", category=IncompleteFieldDefinitionWarning)
except ImportError:
    pass

from mcp.server.fastmcp import FastMCP

from .tools.errors import InvalidJsonError, error_response
from .tools.gap_analyzer import format_gap_report
from .tools.methodology import build_methodology_context
from .tools.plan_importer import parse_plan_file
from .tools.roadmap import format_roadmap, parse_roadmap
from .tools.profile import (
    load_profile,
    merge_section,
    save_plan_snapshot,
    save_profile,
)
from .models import JourneyEntry
from .tools.resume_parser import extract_text
from .tools.session import get_welcome_message
from .scrapers import list_scrapers, search_company_jobs, get_job_detail
from .scrapers.loader import read_scraper_guide

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
    """特定企业使用教程（与 get_scraper_guide 工具同源）"""
    path = Path(__file__).parent / "scrapers" / scraper_id / "guide.md"
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


def _json(obj: Any) -> str:
    """将对象序列化为 JSON 字符串。

    MCP 工具返回类型必须是 str，返回 dict 会触发 FastMCP schema 校验失败。
    所有工具的结构化返回值必须经过本函数。
    """
    return json.dumps(obj, ensure_ascii=False, indent=2)


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
        section: 填充到哪个 section，只接受 who / have / want
            - who: 你是谁（姓名、教育、状态）
            - have: 你有什么（技能、经历、资源）；关键技能请附带证据与置信度
            - want: 你想要什么（目标岗位、行业、薪资）
        data: 用户提供的信息，必须是 JSON 对象字符串
            示例：'{"name":"张三", "education":"计算机本科", "skills":["Python", "React"]}'
            非法 JSON 会被拒绝且不写入档案
    """
    if section not in ("who", "have", "want"):
        return error_response(
            "INVALID_SECTION",
            f"section 必须是 who/have/want，收到的是「{section}」",
            {"received": section, "valid": ["who", "have", "want"]},
        )

    # 先校验再写入：坏 JSON 静默入库会污染工作流状态判定（BUG-007）
    try:
        _parse_json_param(data, f"{section} 数据")
    except InvalidJsonError as exc:
        return error_response(exc.code, exc.message, exc.details)

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
    profile.section_updated_at["target_jd"] = datetime.now().isoformat()
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

    返回方法论上下文。LLM 按照方法论指引，基于已抓取的真实数据
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

    return _json({
        "methodologies": [ctx1["methodology"], ctx2["methodology"]],
        "profile": ctx1["profile"],
        "existing_journey": [
            {"phase": j.phase, "decision": j.decision, "timestamp": j.timestamp}
            for j in (profile.journey or [])[-5:]
        ],
        "instructions": (
            "请按照上述方法论指引：\n"
            "1. 先用 fetch_company_jobs 搜索目标企业的真实岗位（先 list_data_sources 查看可用企业）\n"
            "2. 用 fetch_jd_detail 获取 JD 全文和同背景案例\n"
            "3. 基于真实数据从简历过筛和面试通过两个维度分析差距\n"
            "4. 调用 save_gap_analysis(gap_json) 保存结构化结果"
        ),
    })


@mcp.tool()
def save_gap_analysis(gap_json: str) -> str:
    """保存差距分析结果。

    何时调用：在 analyze_gaps 返回分析任务，LLM 完成分析后调用此工具保存结果。

    Args:
        gap_json: 差距分析的 JSON 字符串

    Schema（与 sop/resume_screening.yaml、sop/interview_prep.yaml 的 output_schema 一致）:
        {
            "match_score": 65,            // 匹配度评分（0-100）
            "match_level": "partial_match",
            "strengths": [                // 优势（对象数组）
                {
                    "area": "前端开发",             // 领域
                    "description": "1年经验",       // 描述
                    "resume_highlight": "...",      // 可选：简历怎么写
                    "interview_talk": "..."         // 可选：面试怎么讲
                }
            ],
            "resume_optimization": {      // 简历过筛维度
                "ats_keywords": ["Python", "Agent"],
                "missing_keywords": ["RAG"],
                "highlight_projects": [
                    {"project": "...", "how_to_package": "...", "quantified_result": "..."}
                ],
                "resume_tips": ["..."],
                "missing_experiences": [
                    {"experience": "...", "how_to_create": "..."}
                ]
            },
            "interview_preparation": {    // 面试通过维度
                "must_prepare": [
                    {"topic": "...", "type": "八股|项目|场景", "priority": "high",
                     "estimated_time": "...", "prepare_advice": "..."}
                ],
                "project_deep_dive": [
                    {"project": "...", "likely_questions": ["..."],
                     "key_points": ["..."], "star_story": "S:... T:... A:... R:..."}
                ],
                "system_design_topics": [{"topic": "...", "framework": "..."}],
                "behavioral_questions": [{"question": "...", "story_template": "..."}],
                "study_plan": {"week_1": ["..."], "week_2": ["..."]}
            },
            "skill_gaps": [               // 技能差距（对象数组）
                {
                    "skill": "TypeScript",
                    "priority": "high",          // high/medium/low
                    "current_level": "无",
                    "required_level": "熟练",    // 注意：字段名是 required_level
                    "is_hidden": false,          // 可选：true 表示 JD 未写但实际考核
                    "how_to_improve": "...",
                    "source": "BOSS直聘 JD"      // 数据来源，必填
                }
            ],
            "priority_actions": [         // 优先行动项（对象数组）
                {"action": "学习 TypeScript 基础", "timeline": "...", "impact": "...", "difficulty": "..."}
            ],
            "market_context": "..."       // 市场背景（来自真实抓取数据汇总）
        }
    """
    try:
        gap_data = _parse_json_param(gap_json, "差距分析")
    except InvalidJsonError as exc:
        return error_response(exc.code, exc.message, exc.details)

    # 先生成报告——格式非法时在此暴露，避免把半成品写进档案
    report = format_gap_report(gap_data)

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

    return _json({
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
    })


@mcp.tool()
def generate_roadmap() -> str:
    """基于差距分析生成分阶段职业路线图。

    返回方法论上下文。LLM 按照方法论指引，结合差距分析结果，
    设计分阶段路线图，然后调用 save_roadmap(roadmap_json) 保存。

    前置条件：差距分析已完成（save_gap_analysis 已调用）。
    后续步骤：LLM 生成路线图后调用 save_roadmap，然后调用 generate_tasks。
    """
    profile = load_profile()

    if not profile.gap:
        return error_response(
            "MISSING_DATA",
            "请先调用 analyze_gaps 完成差距分析，再生成路线图。",
            {"missing": "gap"},
        )

    ctx = build_methodology_context("roadmap", profile)

    return _json({
        "methodology": ctx["methodology"],
        "profile": ctx["profile"],
        "instructions": (
            "请按照路线图方法论指引：\n"
            "1. 基于已保存的差距分析（gap）和之前搜索的真实 JD 数据\n"
            "2. 设计分阶段路线图，每个任务标注来源依据\n"
            "3. 调用 save_roadmap(roadmap_json) 保存结构化结果"
        ),
    })


@mcp.tool()
def save_roadmap(roadmap_json: str) -> str:
    """保存路线图到档案。

    Args:
        roadmap_json: 路线图的 JSON 字符串

    Schema（与 sop/roadmap.yaml 一致）:
        {
            "strategy_summary": "整体策略说明",
            "phases": [                  // 阶段列表
                {
                    "type": "learn",              // learn/project/intern/research
                    "name": "基础学习",           // 阶段名称
                    "goal": "掌握基础",           // 阶段目标
                    "kpi": {"metric": "...", "target": "...", "evidence": "..."},
                    "resume_value": "",           // project/intern/research 必填
                    "milestones": [               // 里程碑列表
                        {
                            "name": "Python 基础",        // 里程碑名称
                            "done_criteria": "能独立写出...", // 完成标准
                            "deliverable": "",             // 交付物
                            "tasks": [                     // 任务列表
                                {
                                    "name": "学习装饰器",      // 任务名称
                                    "description": "...",     // 可选
                                    "priority": "high"        // 可选
                                }
                            ]
                        }
                    ]
                }
            ]
        }

    注意：不要输出任何时长类字段（duration/estimated_days 等），产品不规划时间。
    """
    try:
        roadmap_data = _parse_json_param(roadmap_json, "路线图")
    except InvalidJsonError as exc:
        return error_response(exc.code, exc.message, exc.details)

    profile = load_profile()

    # 保存旧版本快照
    if profile.plan:
        save_plan_snapshot(source="before_roadmap")

    # 解析并写入 plan；新路线图 = 新阶段体系，历史审计记录作废
    parsed = parse_roadmap(json.dumps(roadmap_data, ensure_ascii=False))
    profile.plan = parsed
    profile.audited_phases = []
    profile.plan_saved_at = datetime.now().isoformat()
    profile.section_updated_at["plan"] = profile.plan_saved_at
    profile.touch()
    save_profile(profile)

    # 保存新版本快照
    save_plan_snapshot(source="roadmap_generated")

    # 格式化报告
    report = format_roadmap(parsed)

    return _json({
        "message": (
            f"路线图已保存。\n\n{report}\n\n"
            "接下来可以调用 generate_tasks 生成任务列表开始执行。"
        ),
        "next_steps": ["generate_tasks"],
        "context": {"phase": "roadmap_saved", "version": profile.version},
    })


@mcp.tool()
def search_knowledge(query: str) -> str:
    """检索本地知识库（用户积累的求职资料）。

    只搜索本地 data/knowledge/ 目录：scraper 抓取自动存入的 JD/面经，
    以及用户手动放入的简历、市场资料。不联网，不调用 LLM。

    何时调用：
    - 分析前查找已积累的同背景案例、目标公司 JD
    - 查询之前抓取过的面经内容

    Args:
        query: 搜索关键词
            示例："AI Agent 面经"、"字节跳动 JD"、"双非 转 AI"

    Returns:
        每条含来源文件路径、相关度、内容预览。
        无结果时返回下一步指引（用 fetch_company_jobs 抓取）——
        此时不要基于自身知识编造市场数据。
    """
    from .tools.knowledge_search import search_knowledge as do_search

    result = do_search(query)
    results = result["results"]

    if not results:
        return (
            f"【知识库检索】{query}\n\n"
            "知识库中暂无相关资料。\n\n"
            "下一步建议：\n"
            "1. 调用 fetch_company_jobs 抓取实时岗位数据（自动存入知识库）\n"
            "2. 用 fetch_jd_detail 获取 JD 全文\n"
            "3. 不要基于 LLM 自身知识编造市场数据——分析必须基于真实数据"
        )

    lines = [f"【知识库检索】{query} — 找到 {result['count']} 条：\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **来源**: {r['source']}（相关度 {r['relevance']}）")
        preview = r["content"][:300].replace("\n", " ")
        lines.append(f"   {preview}")
        lines.append("")

    lines.append("需要完整内容时，直接读取对应文件路径。")
    lines.append("如需更多实时数据，调用 fetch_company_jobs。")
    return "\n".join(lines)


@mcp.tool()
def import_plan(file_path: str) -> str:
    """导入已有的职业规划文档。

    支持 PDF、DOCX、Markdown、TXT 格式。
    如果已有计划，会在对话中对比新旧内容，由用户决定取舍。

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

    # 如果没有旧计划，提示 LLM 走标准路线图链路导入
    if not profile.plan:
        return (
            f"--- PLAN CONTENT ---\n{new_plan_text}\n--- END ---\n\n"
            "这是新导入的计划文档。请将其整理为路线图结构后调用 save_roadmap(roadmap_json) 保存：\n"
            "schema 参考 sop/roadmap.yaml 的 output_schema（任务字段为 name/description/priority）。"
        )

    # 有旧计划时：对比与取舍在对话中完成，落盘走 save_roadmap
    return (
        f"--- NEW PLAN CONTENT ---\n{new_plan_text}\n--- END ---\n\n"
        "检测到已有计划档案。请在对话中向用户呈现新旧计划的差异，"
        "由用户决定保留哪些内容；确认后把最终版整理为路线图结构，调用 save_roadmap(roadmap_json) 保存。"
    )


@mcp.tool()
def get_scraper_guide(company: str) -> str:
    """获取指定企业数据源的完整使用教程。

    何时调用：第一次使用某个数据源前（或在 fetch_company_jobs 报错后）调用，
    了解该源能搜什么、参数语义、返回字段、登录要求和失败处理。

    Args:
        company: 企业 ID（通过 list_data_sources 获取）
            示例：bytedance
    """
    guide = read_scraper_guide(company)
    if guide is None:
        available = ", ".join(s["id"] for s in list_scrapers()) or "无"
        return (
            f"「{company}」没有使用指南或不是已注册的数据源。\n"
            f"可用数据源：{available}"
        )
    return guide


@mcp.tool()
def list_data_sources() -> str:
    """列出所有已注册的企业招聘数据源。

    何时调用：第一次需要真实岗位/面经数据时先调用本工具，
    看有哪些源、各支持什么参数；然后用 get_scraper_guide(company)
    查看目标源的完整教程（返回字段、示例、注意事项），再调 fetch_company_jobs。
    """
    scrapers = list_scrapers()

    if not scrapers:
        return "暂无已注册的企业数据源。社区贡献请参考 src/scrapers/ 目录。"

    lines = ["【已注册企业招聘数据源】\n"]
    for s in scrapers:
        lines.append(f"## {s['name']}（ID: {s['id']}）")
        if s.get("description"):
            lines.append(f"  {s['description']}")

        params = s.get("params", {})
        if params:
            lines.append("  支持的搜索参数：")
            for pname, pinfo in params.items():
                req = "（必填）" if isinstance(pinfo, dict) and pinfo.get("required") else "（可选）"
                desc = pinfo.get("description", "") if isinstance(pinfo, dict) else str(pinfo)
                lines.append(f"    - {pname}{req}: {desc}")

        lines.append(f"  详细用法：get_scraper_guide(company=\"{s['id']}\")")
        lines.append("")

    lines.append("---")
    lines.append("使用原则：params 只传上表列出的参数，不要自造参数名；")
    lines.append("搜索失败时按错误信息处理，不要编造岗位数据。")
    return "\n".join(lines)


@mcp.tool()
async def fetch_company_jobs(company: str, params: str = "{}") -> str:
    """搜索指定企业的岗位或面经（实时抓取真实数据）。

    何时调用：需要真实岗位数据（差距分析、路线图、薪资行情）或面经数据时调用。
    前置条件：先调用 list_data_sources 查看该企业支持的参数，params 只传列出的参数。

    Args:
        company: 企业 ID（通过 list_data_sources 获取）
            示例：bytedance
        params: 搜索参数 JSON 字符串（各企业支持的参数不同）
            示例：'{"keyword":"AI Agent", "city":"北京"}'

    Returns:
        每行一个岗位：标题 | 地点 | 薪资（如有）、链接、内容摘要。
        boss/bytedance 返回岗位（含薪资范围）；nowcoder 返回面经。
        失败时返回错误原因和恢复建议——此时如实告知用户，不要编造数据。
    """
    try:
        params_dict = json.loads(params) if params else {}
    except (json.JSONDecodeError, TypeError) as exc:
        return error_response(
            "INVALID_JSON",
            f"params JSON 解析失败：{exc}",
            {"raw": params[:200]},
        )

    # 抓取是阻塞 IO（含 Playwright 同步 API），移入工作线程执行，
    # 避免在事件循环线程内触发 "Sync API inside asyncio loop" 崩溃
    result = await asyncio.to_thread(search_company_jobs, company, **params_dict)

    if result.get("error"):
        return error_response(
            "ANALYSIS_FAILED",
            result["error"],
            {
                "available": result.get("available", []),
                "recovery": (
                    "可尝试：1) 换关键词重试 2) 换其他企业数据源 "
                    "3) 如确认数据不可用，如实告知用户，不要编造岗位数据"
                ),
            },
        )

    count = result["count"]
    company_name = result["company"]

    if count == 0:
        return (
            f"「{company_name}」未找到匹配的岗位。\n\n"
            "建议：1) 换更宽泛的关键词重试 2) 尝试其他企业数据源（list_data_sources 查看）"
        )

    # 部分失败的警告信息
    warnings_list = result.get("warnings", [])

    lines = [f"【{company_name}】找到 {count} 个岗位：\n"]
    for i, job in enumerate(result["results"], 1):
        title = job.get("title", "未知岗位")
        location = job.get("location", "")
        salary = job.get("salary", "")
        url = job.get("url", "")

        loc_str = f" | {location}" if location else ""
        sal_str = f" | {salary}" if salary else ""
        lines.append(f"{i}. **{title}**{loc_str}{sal_str}")
        if url:
            lines.append(f"   链接：{url}")
        # 兼容 JD 类（summary）和面经类（snippet）字段名
        preview = job.get("summary") or job.get("snippet") or ""
        if preview:
            lines.append(f"   {preview[:100]}")
        lines.append("")

    if warnings_list:
        lines.append("---")
        lines.append("⚠️ 部分数据获取失败：")
        for w in warnings_list:
            lines.append(f"   - {w}")
        lines.append("")

    lines.append("获取岗位详情：fetch_jd_detail(url=\"具体岗位URL\")")
    lines.append("薪资行情可直接汇总以上各岗位的薪资范围，这是最真实的市场数据。")
    return "\n".join(lines)


@mcp.tool()
async def fetch_jd_detail(url: str, company: str = "") -> str:
    """获取岗位详情或面经全文（JD 完整描述、任职要求）。

    何时调用：fetch_company_jobs 结果中某个岗位/面经需要深入分析时调用。
    url 必须来自 fetch_company_jobs 的返回结果。

    Args:
        url: 岗位详情页 URL（来自 fetch_company_jobs 结果）
        company: 企业 ID（可选，不填则自动按 URL 匹配 Scraper）

    Returns:
        岗位：标题、公司、地点、薪资（如有）、岗位描述全文、任职要求。
        面经：标题、面试问题与经验全文。
    """
    # 同 fetch_company_jobs：阻塞抓取移入工作线程，规避事件循环内的同步 Playwright
    result = await asyncio.to_thread(get_job_detail, url, company if company else None)

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

    何时调用：在 save_roadmap 之后调用，将路线图转化为可执行的任务。
    前置条件：档案中已有路线图（plan.roadmap）。
    后续步骤：调用 get_next_tasks 查看当前阶段的下一步任务。

    注意：重建会清空旧任务列表；已完成的进度会自动沉淀为能力证据写入档案，不会丢失。
    """
    from .tools.task_manager import (
        collect_completed_evidence,
        create_tasks_from_roadmap,
        format_task_list,
    )

    profile = load_profile()

    if not profile.plan.get("roadmap") and not profile.plan.get("phases"):
        return error_response(
            "MISSING_DATA",
            "档案中没有路线图，请先调用 generate_roadmap。",
            {"section": "plan"},
        )

    # 重建前：把已完成/已跳过的进度沉淀为能力证据（目标变了，努力不白费）
    evidence = collect_completed_evidence(profile)
    if evidence:
        have_evidence = profile.have.setdefault("capability_evidence", [])
        if isinstance(have_evidence, list):
            have_evidence.extend(evidence)

    # 清空旧任务并从路线图生成
    profile.tasks = []
    tasks = create_tasks_from_roadmap(profile)

    for task in tasks:
        profile.add_task(task)

    save_profile(profile)

    migrated_note = (
        f"已将 {len(evidence)} 条历史完成记录沉淀为能力证据。\n" if evidence else ""
    )
    return _json({
        "message": f"{migrated_note}已从路线图生成 {len(tasks)} 个任务。",
        "tasks": format_task_list(tasks, "生成的任务"),
        "next_steps": ["get_next_tasks"],
        "context": {"phase": "tasks_generated", "task_count": len(tasks)},
    })


@mcp.tool()
def get_next_tasks() -> str:
    """获取当前阶段的下一步任务。

    何时调用：用户想知道「现在该做什么」时调用。
    返回当前阶段（第一个有未完成任务的阶段）的接下来几个任务和阶段进度。
    产品不规划时间——顺序归产品，时间归用户。
    """
    from .tools.task_manager import current_phase_view, format_progress_overview

    profile = load_profile()

    if not profile.tasks:
        return _json({
            "message": "暂无任务。请先调用 generate_tasks 从路线图生成任务。",
            "next_steps": ["generate_tasks"],
            "context": {"phase": "no_tasks"},
        })

    view = current_phase_view(profile)

    lines = []

    if view is None:
        lines.append("🎉 所有阶段已完成！建议回顾目标，规划下一步方向。")
        next_step = "trigger_insight(event)"
    else:
        pct = int(view["done"] / view["total"] * 100) if view["total"] else 0
        lines.append(f"## 🎯 当前阶段：{view['phase_name']}（{view['done']}/{view['total']}，{pct}%）")
        lines.append("")
        lines.append("### 接下来做")
        for t in view["next_tasks"]:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t.priority, "⚪")
            status_mark = "🔵" if t.status == "in_progress" else icon
            desc = f"—{t.description}" if t.description else ""
            lines.append(f"- {status_mark} **{t.name}** (ID: {t.id}){desc}")
        lines.append("")
        next_step = "checkin_task"

    lines.append(format_progress_overview(profile))
    lines.append("---")
    lines.append("完成任务后，请调用 checkin_task 打卡。")
    lines.append("节奏由用户掌握：快了可以加深或推进下一项，慢了随时调整顺序。")

    return "\n".join(lines)


@mcp.tool()
def checkin_task(task_id: str, status: str = "completed", notes: str = "") -> str:
    """打卡任务。

    何时调用：用户完成或跳过某个任务时调用。
    完成的任务会沉淀为能力证据写入档案。

    Args:
        task_id: 任务 ID（从 get_next_tasks 获取）
        status: 打卡状态（completed 或 skipped）
        notes: 备注（可选）
    """
    from .tools.task_manager import (
        checkin_task as do_checkin,
        format_progress_overview,
        record_capability_evidence,
    )
    from .tools.insight import completed_phase_ids

    profile = load_profile()

    try:
        profile, checkin = do_checkin(profile, task_id, status, notes)
    except ValueError as e:
        return error_response("MISSING_DATA", str(e), {"task_id": task_id})

    task = profile.get_task(task_id)

    # 能力证据沉淀
    if status == "completed" and task:
        record_capability_evidence(profile, task, notes)

    # 阶段完成检测（排除已审计过的阶段）
    newly_completed = [pid for pid in completed_phase_ids(profile) if pid not in profile.audited_phases]

    lines = []
    lines.append(f"✅ 已打卡：{task.name if task else task_id}")
    if status == "skipped":
        lines[0] = f"⏭️ 已跳过：{task.name if task else task_id}"
    lines.append("")

    if newly_completed:
        lines.append(f"🎯 恭喜！你完成了阶段「{newly_completed[0]}」的全部任务。")
        lines.append("建议调用 trigger_insight(trigger_type=\"stage_audit\") 进行阶段审计。")
        lines.append("")

    if status == "completed" and task:
        lines.append("💡 如果完成得轻松，可以考虑加深难度或直接推进下一项——由你和用户在对话中决定。")

    save_profile(profile)

    lines.append("")
    lines.append(format_progress_overview(profile))

    return "\n".join(lines)


@mcp.tool()
def trigger_insight(trigger_type: str = "stage_audit", event_description: str = "") -> str:
    """触发洞察检查。

    何时调用：
    - 用户完成阶段后（trigger_type="stage_audit"）
    - 用户报告事件时（trigger_type="event"，如拿到面试、目标变更）

    工作流程：
    1. 调用 trigger_insight 获取分析 prompt
    2. LLM 根据 prompt 分析用户进度
    3. LLM 生成洞察 JSON
    4. 调用 apply_insight(insight_json) 应用结果

    Args:
        trigger_type: 触发类型（stage_audit / event）
        event_description: 事件描述（当 trigger_type 为 event 时必填）

    Returns:
        包含分析 prompt 和使用说明的字典
    """
    from .tools.insight import VALID_TRIGGER_TYPES, build_insight_prompt

    if trigger_type not in VALID_TRIGGER_TYPES:
        return error_response(
            "INVALID_SECTION",
            f"trigger_type 必须是 stage_audit/event，收到的是「{trigger_type}」",
            {"received": trigger_type, "valid": list(VALID_TRIGGER_TYPES)},
        )

    profile = load_profile()

    if not profile.tasks:
        return _json({
            "message": "暂无任务，请先调用 generate_tasks。",
            "next_steps": ["generate_tasks"],
            "context": {"phase": "no_tasks"},
        })

    # 构建 prompt
    prompt = build_insight_prompt(profile, trigger_type, event_description)

    return _json({
        "message": "洞察分析任务已准备。请根据以下 prompt 进行分析，然后调用 apply_insight 应用结果。",
        "prompt": prompt,
        "output_format": {
            "trigger_type": trigger_type,
            "status": "on_track|behind|ahead|need_adjustment",
            "summary": "进度总结",
            "insights": ["洞察1", "洞察2"],
            "adjustment_needed": True,
            "adjustment_reason": "调整原因",
            "changes": [{"type": "add_task|remove_task|modify_task", "task_id": "task_001", "details": {}}],
            "user_message": "给用户的消息"
        },
        "next_steps": ["apply_insight"],
        "context": {"phase": "insight_ready", "trigger_type": trigger_type},
    })


@mcp.tool()
def apply_insight(insight_json: str) -> str:
    """应用洞察分析结果到档案。

    何时调用：在 trigger_insight 之后，LLM 分析完成后调用。

    Args:
        insight_json: LLM 返回的洞察分析 JSON

    Schema:
        {
            "trigger_type": "stage_audit",  // 回传触发类型：stage_audit/event
            "status": "on_track",        // 状态：on_track/behind/ahead/need_adjustment
            "summary": "进度正常",        // 进度总结
            "insights": [                // 洞察列表
                "学习速度超预期",
                "可以加深难度"
            ],
            "adjustment_needed": false,  // 是否需要调整
            "adjustment_type": "auto",   // 调整类型：auto/manual
            "adjustment_reason": "",     // 调整原因
            "changes": [                 // 调整列表（产品不规划时间，无压缩时长类调整）
                {
                    "type": "add_task",       // 类型：add_task/remove_task/modify_task
                    "task_id": "task_001",    // 任务 ID（add_task 时省略）
                    "details": {              // 详情
                        "name": "新任务名"
                    }
                }
            ],
            "user_message": "给用户的消息"
        }
    """
    from .tools.insight import (
        apply_adjustment,
        format_insight_report,
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

        return _json({
            "message": "已应用调整。",
            "report": format_insight_report(insight_result),
            "adjustment": adjustment.model_dump(),
            "context": {"phase": "adjustment_applied"},
        })
    else:
        return _json({
            "message": "无需调整。",
            "report": format_insight_report(insight_result),
            "context": {"phase": "insight_complete"},
        })


@mcp.tool()
def get_progress() -> str:
    """获取进度概览。

    何时调用：用户想查看整体进度时调用。
    返回任务统计、打卡记录、调整历史。
    """
    from .tools.task_manager import format_progress_overview

    profile = load_profile()

    if not profile.tasks:
        return _json({
            "message": "暂无任务。请先调用 generate_tasks 从路线图生成任务。",
            "next_steps": ["generate_tasks"],
            "context": {"phase": "no_tasks"},
        })

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

    # 目标变更检测：want / target_jd 在路线图保存之后被更新过 → 建议重新分析
    goal_change_alert = ""
    plan_saved_at = profile.plan_saved_at
    if profile.plan.get("roadmap") and plan_saved_at:
        for key in ("want", "target_jd"):
            updated_at = profile.section_updated_at.get(key, "")
            if updated_at and updated_at > plan_saved_at:
                goal_change_alert = (
                    f"⚠️ 检测到目标（{key}）在路线图生成之后发生了变更。\n"
                    "旧路线图可能已不适用，建议重新调用 analyze_gaps 进行分析。\n\n"
                )
                break

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
        phase = "execution_prep"
        if not profile.tasks:
            next_step = "generate_tasks"
        else:
            completed_steps.append("generate_tasks")

    if profile.tasks:
        phase = "execution"
        finished_status = ("completed", "skipped")
        all_finished = all(t.status in finished_status for t in profile.tasks)

        if all_finished:
            phase = "completed"
            next_step = "目标达成！可回顾目标，规划下一步。"
        else:
            next_step = "get_next_tasks"

    # 构建状态报告
    total_tasks = len(profile.tasks)
    completed_tasks = sum(1 for t in profile.tasks if t.status == "completed")

    lines = []
    lines.append(f"## 当前状态：{phase}")
    lines.append("")
    if goal_change_alert:
        lines.append(goal_change_alert.rstrip())
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
    lines.append("")
    lines.append("### 工作流指南")
    lines.append("- 建档：start_session → intake(who/have/want) → finalize_profile")
    lines.append("- 分析：analyze_gaps → save_gap_analysis")
    lines.append("- 规划：generate_roadmap → save_roadmap → generate_tasks")
    lines.append("- 执行：get_next_tasks → checkin_task → trigger_insight(stage_audit/event) → apply_insight")
    lines.append("- 产出：export_dashboard 生成阶段进度仪表盘")
    lines.append("")
    lines.append("节奏原则：顺序归产品，时间归用户——不为任务设定时限。")

    return "\n".join(lines)


@mcp.tool()
def export_dashboard() -> str:
    """生成阶段进度仪表盘（自包含 HTML 文件）。

    何时调用：用户想直观查看整体进度时调用。
    一次性产出：HTML 内嵌当前档案数据快照，双击即可在浏览器查看，无需服务器。
    """
    import tempfile

    profile = load_profile()

    finished_status = ("completed", "skipped")
    total_tasks = len(profile.tasks)
    completed = sum(1 for t in profile.tasks if t.status == "completed")
    skipped = sum(1 for t in profile.tasks if t.status == "skipped")

    # 阶段视图
    roadmap = profile.plan.get("roadmap", profile.plan)
    phases_html = ""
    phases = roadmap.get("phases", []) if isinstance(roadmap, dict) else []
    for idx, phase in enumerate(phases):
        phase_id = phase.get("id") or f"phase_{idx + 1}"
        phase_tasks = [t for t in profile.tasks if t.phase_id == phase_id]
        done = sum(1 for t in phase_tasks if t.status in finished_status)
        pct = int(done / len(phase_tasks) * 100) if phase_tasks else 0
        audited = "✓ 已审计" if phase_id in profile.audited_phases else ""
        phases_html += (
            f'<div class="phase"><div class="phase-head"><span>{phase.get("name", phase_id)}</span>'
            f'<span>{done}/{len(phase_tasks)}{audited}</span></div>'
            f'<div class="bar"><div class="fill" style="width:{pct}%"></div></div>'
            f'<p class="goal">{phase.get("goal", "")}</p></div>'
        )

    # 当前阶段任务
    current_html = "<p>暂无任务。</p>"
    open_tasks = [t for t in profile.tasks if t.status not in finished_status]
    if open_tasks:
        items = "".join(
            f"<li>{t.name}{f' <small>({t.phase_id})</small>' if t.phase_id else ''}</li>"
            for t in open_tasks[:8]
        )
        current_html = f"<ul>{items}</ul>"

    # 能力证据
    evidence = profile.have.get("capability_evidence", [])
    evidence_items = "".join(
        f"<li><b>{e.get('task', '')}</b>"
        f"{f' — {e["notes"]}' if e.get('notes') else ''}</li>"
        for e in evidence[-10:] if isinstance(e, dict)
    ) or "<li>暂无——完成任务打卡后自动沉淀</li>"
    evidence_html = f"<ul>{evidence_items}</ul>"

    # 调整历史
    adj_items = "".join(
        f"<li><b>{a.timestamp[:10]}</b> {a.reason or a.trigger}</li>"
        for a in reversed(profile.adjustments[-5:])
    ) or "<li>暂无调整记录</li>"
    adjustments_html = f"<ul>{adj_items}</ul>"

    overall_pct = int(completed / total_tasks * 100) if total_tasks else 0

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>Career Kit 进度仪表盘</title>
<style>
body {{ font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
       max-width: 760px; margin: 0 auto; padding: 24px; color: #222; background: #fafafa; }}
h1 {{ font-size: 22px; }} h2 {{ font-size: 17px; border-bottom: 2px solid #4a90d9; padding-bottom: 4px; }}
.card {{ background: #fff; border: 1px solid #e3e3e3; border-radius: 10px; padding: 16px; margin-bottom: 16px; }}
.bar {{ background: #eee; border-radius: 6px; height: 12px; overflow: hidden; }}
.fill {{ background: linear-gradient(90deg,#4a90d9,#67b26f); height: 100%; }}
.phase {{ margin-bottom: 14px; }}
.phase-head {{ display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 4px; }}
.goal {{ color: #666; font-size: 13px; margin: 4px 0 0; }}
small, .meta {{ color: #999; font-size: 12px; }}
ul {{ padding-left: 20px; }} li {{ margin: 4px 0; font-size: 14px; }}
.overall {{ display: flex; align-items: center; gap: 12px; }}
.overall .num {{ font-size: 30px; font-weight: 700; color: #4a90d9; }}
</style>
</head>
<body>
<h1>Career Kit 进度仪表盘 <span class="meta">生成于 {datetime.now().strftime("%Y-%m-%d %H:%M")} · 快照 v{profile.version}</span></h1>

<div class="card overall"><span class="num">{overall_pct}%</span>
  <div style="flex:1"><div class="bar"><div class="fill" style="width:{overall_pct}%"></div></div>
  <p class="goal">共 {total_tasks} 个任务 · 完成 {completed} · 跳过 {skipped} · 目标：{profile.want.get('target_role', '未设定')}</p></div>
</div>

<div class="card"><h2>阶段进度（顺序推进，节奏自定）</h2>
{phases_html or '<p>尚未生成路线图。</p>'}</div>

<div class="card"><h2>接下来做</h2>{current_html}</div>

<div class="card"><h2>能力证据（来自打卡沉淀）</h2>{evidence_html}</div>

<div class="card"><h2>调整历史</h2>{adjustments_html}</div>

<p class="meta">顺序归产品，时间归用户 —— Career Kit 不为任务设定时限。</p>
</body></html>"""

    out_path = Path(tempfile.gettempdir()) / "career_kit_dashboard.html"
    out_path.write_text(html, encoding="utf-8")

    return (
        f"仪表盘已生成：{out_path}\n\n"
        "用浏览器打开即可查看。数据为生成时刻的快照，进度更新后可重新导出。\n"
        "如需日程表，请直接在对话中为用户编写 markdown/HTML 日程文档（时间由用户自己填）。"
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
