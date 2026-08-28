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
    delete_profile as do_delete_profile,
    get_active_profile_name,
    list_profiles as do_list_profiles,
    list_trash as do_list_trash,
    load_profile,
    merge_section,
    profile_exists,
    restore_profile as do_restore_profile,
    save_plan_snapshot,
    save_profile,
    set_active_profile_name,
    validate_profile_name,
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
        f"当前档案：{get_active_profile_name()}\n"
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
    result = f"已记录到「{section}」。当前档案版本：v{profile.version}"

    # 毕业届引导（届别校验的数据基础）：who 未含 graduation_year 时提醒补充
    if section == "who":
        who = profile.who or {}
        if not who.get("graduation_year") and not who.get("graduation"):
            result += (
                "\n\n毕业届提示：届别校验（路线图不排用户投不进的岗位）需要毕业年份。"
                "若方便请补充：intake(section='who', data='{\"graduation_year\": \"2028\"}')（如 2028 届）。"
                "不补充也不影响流程，届别校验会自动跳过。"
            )

    return result


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

    # 摸排提醒（BUG-015）：have 有技能但没有任何证据/置信度标注时，先摸真实水平再放行。
    # 简历有美化成分——按简历字面水平做差距分析会系统性失真。
    have = profile.have or {}
    skills = have.get("skills", [])
    has_evidence = bool(
        have.get("evidence")
        or have.get("skill_evidence")
        or have.get("capability_evidence")
        or any(isinstance(s, dict) and (s.get("evidence") or s.get("confidence")) for s in skills)
    )
    probe_reminder = ""
    if skills and not has_evidence:
        probe_reminder = (
            "\n\n 摸排提醒：have 中的技能没有任何证据/置信度标注。\n"
            "在继续 analyze_gaps 之前，请先对关键技能逐项追问证据：\n"
            "  做过什么项目？现场讲一个难点？实际掌握到什么程度？\n"
            "然后把证据（evidence）与置信度（confidence）补充进 have 后再进入分析。\n"
            "原因：简历有美化成分，基于美化后的水平做差距分析会严重失真。"
        )

    # 目标缺失提醒：没有明确方向时不应直接 analyze_gaps，应先 explore_goals
    goal_reminder = ""
    if not _has_goal(profile):
        goal_reminder = (
            "\n\n目标缺失：档案中还没有明确的职业方向（want 只有模糊表述或为空）。\n"
            "先调用 explore_goals 用三轴定位（能力×兴趣×真实市场数据）帮用户选定方向，"
            "再用 intake(section='want') 落定，然后才进入 analyze_gaps。"
        )

    return (
        f"档案已确认。\n\n摘要：{profile.summary}{probe_reminder}{goal_reminder}\n\n"
        "可以开始分析差距了，请调用 analyze_gaps。"
    )


def _summarize_dict(d: dict) -> str:
    """将字典转为简洁的文本摘要。"""
    items = [f"{k}={v}" for k, v in d.items() if k != "raw"]
    if not items and "raw" in d:
        return str(d["raw"])
    return "，".join(items)


def _has_goal(profile) -> bool:
    """是否已有可分析的实质目标（want 关键字段或 target_jd）。

    want 中的 raw（如"想转行"这种模糊表述）不算实质目标——正是 explore_goals 的场景。
    """
    want = profile.want or {}
    for key in ("target_role", "role", "position", "direction", "industry",
                "job_family", "target_company", "target_companies"):
        if want.get(key):
            return True
    if profile.target_jd:
        return True
    return False


@mcp.tool()
def import_jd(jd_text: str) -> str:
    """导入目标岗位的 JD（职位描述）。

    Args:
        jd_text: JD 的结构化 JSON 文本
            示例：'{"company":"字节跳动","role":"AI Agent 工程师","requirements":["LangGraph","RAG"]}'
            空串 / 非 JSON / 非对象输入会被拒绝，不会污染档案。
    """
    # target_jd 只接受结构化 JSON（BUG-010/BUG-011）：
    # 空串、纯文本、非 dict 一律拒绝，绝不静默以 {"raw": text} 入库
    if not jd_text or not jd_text.strip():
        return error_response(
            "INVALID_JSON",
            "JD 内容为空。请提供目标岗位的 JD 文本后重试。",
            {"received": ""},
        )

    try:
        jd_data = json.loads(jd_text)
    except json.JSONDecodeError as exc:
        return error_response(
            "INVALID_JSON",
            "JD 不是合法 JSON。请提供结构化 JD："
            '{"company":..., "role":..., "requirements":[...]}（至少含其中一项）；'
            "或将 JD 文件交给 import_jd_file 解析。",
            {"raw": jd_text[:200], "parse_error": str(exc)},
        )

    if not isinstance(jd_data, dict):
        return error_response(
            "INVALID_JSON",
            f"JD JSON 必须是对象（dict），收到的是 {type(jd_data).__name__}。",
            {"received": jd_text[:200]},
        )

    # 最小校验（BUG-010）：缺岗位业务字段的 JD 拒绝导入，防示例/垃圾污染 target_jd
    biz_fields = (
        "company", "role", "position", "title", "job",
        "requirements", "description", "job_description",
        "responsibilities", "responsibility",
    )
    if not any(jd_data.get(k) for k in biz_fields):
        return error_response(
            "INVALID_JSON",
            "target_jd 缺少岗位关键字段（company/role/requirements/description 等），拒绝导入。"
            "请基于真实 JD 内容填充字段后再调用 import_jd。",
            {"received": jd_text[:200]},
        )

    profile = load_profile()
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
        "根据以上 JD 内容，请调用 import_jd 工具导入，字段结构如下：\n"
        'import_jd(jd_text=\'{"company": "<公司名>", "role": "<岗位名>", "requirements": ["<要求1>", "<要求2>"]}\')\n'
        " 请用上面 JD 的真实内容填充字段（company/role/requirements/description 至少一项），"
        "禁止原样复制示例占位文本。"
    )


@mcp.tool()
def list_profiles() -> str:
    """列出所有职业档案，标记当前使用中的档案。

    何时调用：用户想查看/选择/切换档案，或想知道当前在用哪份档案时。
    多档案场景：一份电脑多人使用、一个人多份规划（转行前后）、测试备份等。

    Returns:
        每个档案：名称、是否当前使用、身份、目标、版本、更新时间。
    """
    profiles = do_list_profiles()

    if not profiles:
        return (
            "当前还没有任何档案。\n\n"
            "开始第一步：调用 start_session 开始建档。"
        )

    active = get_active_profile_name()
    lines = ["【职业档案列表】\n"]
    for p in profiles:
        mark = "[当前使用]" if p["is_active"] else "—"
        person = p.get("person") or "（未填身份）"
        target = p.get("target") or "（未设目标）"
        has_plan = "有路线图" if p.get("has_plan") else ""
        lines.append(
            f"- **{p['name']}** {mark}\n"
            f"  身份：{person}\n"
            f"  目标：{target}\n"
            f"  版本 v{p.get('version', 0)} · 更新于 {p.get('updated_at', '?')[:10]} {has_plan}"
        )
        lines.append("")

    lines.append("---")
    lines.append(f"当前使用：{active}")
    lines.append("切换档案：switch_profile(profile_name=\"<档案名>\")")
    lines.append("删除档案：delete_profile(profile_name=\"<档案名>\")（当前使用的档案不可删除）")
    return "\n".join(lines)


@mcp.tool()
def switch_profile(profile_name: str) -> str:
    """切换当前使用的档案。

    何时调用：用户有多份档案，想切换到另一份继续规划时。
    切换后，所有建档/分析/规划/任务工具都操作新档案。

    Args:
        profile_name: 目标档案名（用 list_profiles 查看可用档案）

    Returns:
        切换结果 + 新档案的当前状态摘要。
    """
    # 先校验命名与存在性，全部通过才写入 active——失败路径不污染当前状态
    try:
        validate_profile_name(profile_name)
    except ValueError as e:
        return error_response("INVALID_SECTION", str(e), {"profile_name": profile_name})

    if not profile_exists(profile_name):
        available = ", ".join(p["name"] for p in do_list_profiles()) or "无"
        return error_response(
            "MISSING_DATA",
            f"档案「{profile_name}」不存在。",
            {"available": available, "hint": "先调用 list_profiles 查看可用档案"},
        )

    set_active_profile_name(profile_name)
    profile = load_profile(profile_name)

    # 未 finalize 的档案 summary 为空，实时从 sections 生成摘要
    summary = profile.summary
    if not summary:
        parts = []
        if profile.who:
            parts.append(f"身份：{_summarize_dict(profile.who)}")
        if profile.have:
            parts.append(f"现状：{_summarize_dict(profile.have)}")
        if profile.want:
            parts.append(f"目标：{_summarize_dict(profile.want)}")
        summary = "；".join(parts) if parts else "（档案为空，尚未建档）"

    return (
        f"已切换到档案「{profile_name}」。\n\n"
        f"档案摘要：{summary}\n\n"
        f"当前状态可调用 get_workflow_status 查看，或继续建档/分析。"
    )


@mcp.tool()
def delete_profile(profile_name: str, confirm: str = "") -> str:
    """删除一份职业档案——移入回收站，可恢复。

    何时调用：用户确认要废弃某份档案时。删除是回收站式的：档案移入
    本地回收站目录（trash/），可用 list_trash 查看、restore_profile 恢复，
    不会真正丢失数据。

    Args:
        profile_name: 要删除的档案名（用 list_profiles 查看可用档案）
        confirm: 必须显式传 "true" 才会执行；其他值只返回确认提示不删除

    Returns:
        删除结果 + 回收站位置 + 恢复指引。
    """
    if confirm != "true":
        return (
            f" 即将删除档案「{profile_name}」——这是不可逆的用户决策，"
            "请先与用户确认（展示该档案的身份/目标/更新时间），确认后重试：\n"
            'delete_profile(profile_name="<档案名>", confirm="true")\n\n'
            "说明：删除是回收站式的，档案会移入本地回收站（trash/），"
            "恢复可用 restore_profile(profile_name=\"<档案名>\")。"
        )

    try:
        target_path = do_delete_profile(profile_name)
    except ValueError as e:
        return error_response("INVALID_SECTION", str(e), {"profile_name": profile_name})

    if target_path is None:
        return error_response(
            "MISSING_DATA",
            f"档案「{profile_name}」不存在。",
            {"hint": "先调用 list_profiles 查看可用档案"},
        )

    remaining = do_list_profiles()
    remain_text = "、".join(p["name"] for p in remaining) or "无（仓库为空）"
    return (
        f"已删除档案「{profile_name}」（移入回收站，可恢复）。\n\n"
        f"回收站位置：{target_path}\n"
        f"剩余档案：{remain_text}\n"
        f"当前使用：{get_active_profile_name()}\n\n"
        "如需恢复：restore_profile(profile_name=\"<档案名>\")"
    )


@mcp.tool()
def list_trash() -> str:
    """列出回收站中的档案（已删除、可恢复项）。

    何时调用：用户想知道删了哪些档案、能否恢复时。
    恢复：restore_profile(profile_name=\"<档案名>\")。
    """
    items = do_list_trash()

    if not items:
        return "回收站为空——还没有删除过任何档案。"

    lines = ["【回收站】已删除档案（可恢复）：\n"]
    for item in items:
        lines.append(
            f"- **{item['profile_name']}**（文件：{item['file']}，删除于 {item['deleted_at'][:19]}）"
        )
    lines.append("")
    lines.append("恢复：restore_profile(profile_name=\"<档案名>\")")
    lines.append("注意：目标位置已存在同名档案时拒绝恢复（防覆盖新数据）。")
    return "\n".join(lines)


@mcp.tool()
def restore_profile(profile_name: str) -> str:
    """从回收站恢复档案。

    何时调用：用户删除档案后又想找回时。恢复的是回收站中最新一份备份；
    目标位置已存在同名档案时拒绝恢复（防覆盖新数据）。

    Args:
        profile_name: 要恢复的档案名（用 list_trash 查看可恢复项）

    Returns:
        恢复结果 + 档案摘要。
    """
    try:
        target_path = do_restore_profile(profile_name)
    except ValueError as e:
        return error_response("INVALID_SECTION", str(e), {"profile_name": profile_name})

    if target_path is None:
        return error_response(
            "MISSING_DATA",
            f"回收站中没有档案「{profile_name}」。",
            {"hint": "先调用 list_trash 查看可恢复项"},
        )

    profile = load_profile(profile_name)
    parts = []
    if profile.who:
        parts.append(f"身份：{_summarize_dict(profile.who)}")
    if profile.have:
        parts.append(f"现状：{_summarize_dict(profile.have)}")
    if profile.want:
        parts.append(f"目标：{_summarize_dict(profile.want)}")
    summary = "；".join(parts) if parts else "（档案为空）"

    return (
        f"已恢复档案「{profile_name}」。\n\n"
        f"档案摘要：{summary}\n\n"
        "如需继续规划，请用 switch_profile(profile_name=\"<档案名>\") 切换到该档案。"
    )


@mcp.tool()
def explore_goals() -> str:
    """目标选择——用户没有明确职业方向时，通过对话探索并选定目标。

    返回方法论上下文。LLM 按照方法论指引，用三轴定位（能力轴=have ×
    兴趣轴=对话挖掘 × 市场轴=fetch_company_jobs 真实数据）提出 2-3 个候选
    方向（带假设与 Fit Filters），引导用户选择，最后用 intake(section="want")
    落定目标。

    何时调用：
    - 用户说"我不知道想做什么" / "帮我选方向" / 完全没有目标时
    - 建档后发现 want 为空或方向模糊（如只有"想转行"没有具体目标）

    前置条件：档案已有 who/have（用户现状）。
    后续步骤：用户选定后 intake(section="want") 写入，然后走 analyze_gaps。
    """
    profile = load_profile()

    if not profile.who and not profile.have:
        return error_response(
            "MISSING_DATA",
            "档案中还没有现状信息（who/have）。请先调用 intake 填充你是谁、会什么，"
            "再帮你探索方向。",
            {"missing": ["who", "have"]},
        )

    # 已有实质目标时先确认：避免用户已有明确方向却被无意义地带入重新探索
    if _has_goal(profile):
        want_summary = _summarize_dict(profile.want or {})
        return (
            f" 档案中已有目标：{want_summary}\n\n"
            "如果用户只是想把现有规划继续推进，直接走 analyze_gaps 即可，无需 explore_goals。\n"
            "如果用户明确想换个方向（如'我之前选的不合适'），则继续本流程重新探索，"
            "选定后用 intake(section='want') 覆盖目标。\n"
            "请先向用户确认意图再决定下一步。"
        )

    # 加载目标选择方法论
    try:
        ctx = build_methodology_context("goal_selection", profile)
    except (FileNotFoundError, ValueError) as e:
        return error_response("MISSING_DATA", f"目标选择方法论加载失败：{e}", {})

    # 记录到 journey
    profile.append_journey(JourneyEntry(
        phase="analysis",
        decision="启动目标选择",
    ))
    save_profile(profile)

    return _json({
        "methodology": ctx["methodology"],
        "profile": ctx["profile"],
        "existing_journey": [
            {"phase": j.phase, "decision": j.decision, "timestamp": j.timestamp}
            for j in (profile.journey or [])[-5:]
        ],
        "instructions": (
            "请按照目标选择方法论指引，通过对话帮用户选定职业方向：\n"
            "1. 先用 get_workflow_status / 档案信息摸清用户现状（零基础就如实对待，不美化）\n"
            "2. 用对话挖掘兴趣轴与约束轴（Genie Goal 式提问，2-3 个问题一轮，不啰嗦）\n"
            "3. 用 list_data_sources → fetch_company_jobs 抓真实岗位数据支撑候选方向，"
            "绝不用 LLM 知识编造'热门方向'\n"
            "4. 主动给出 2-3 个候选方向（标注假设 + Fit Filters + 零基础友好度），让用户纠正\n"
            "5. 引导用户选择（1-10 打分），选定后用 intake(section='want') 写入档案，"
            "如实记录 experience_level\n"
            "6. 提示用户可继续 analyze_gaps 差距分析；方向不合适可随时回来重新探索"
        ),
    })


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

    # 链路守卫：没有实质目标（want 为空/仅模糊表述）时先 explore_goals，
    # 避免对"无目标"做差距分析产出无意义报告
    if not _has_goal(profile):
        return error_response(
            "MISSING_DATA",
            "档案中还没有明确的职业方向（want 为空或只有模糊表述）。",
            {
                "missing": "want",
                "suggestion": (
                    "先调用 explore_goals 用三轴定位（能力×兴趣×真实市场数据）"
                    "帮用户选定方向，再用 intake(section='want') 落定目标后重试。"
                ),
            },
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
        "step_template": [
            {
                "step": 1,
                "name": "起点判定",
                "action": "用 roadmap.yaml 的 start_level_rubric 打分表逐维度评分（学历/实习/协作/技能/项目），"
                          "加权求总分映射档位（大厂/中厂/小厂/暂不可入），输出各维度得分 + 判定依据",
                "output": {"start_level": "档位", "dimension_scores": {"education": 0, "internship": 0, "collaboration": 0, "skill_depth": 0, "project_complexity": 0}, "rationale": "为什么是这个档位"},
                "checkpoint": True,
                "checkpoint_note": "把起点层级展示给用户确认后再进下一步",
            },
            {
                "step": 2,
                "name": "目标拆解",
                "action": "从 want/target_jd 提取目标角色与目标公司层级，计算与 start_level 的跨度，得出过渡级数",
                "output": {"target_role": "", "target_level": "大厂/中厂/小厂", "level_gap": 0, "transition_stages_needed": 0},
                "checkpoint": False,
            },
            {
                "step": 3,
                "name": "阶段序列设计",
                "action": "按起点→目标设计阶段序列（learn/project/intern/...），遵守层级连续铁律："
                          "intern 目标层级 ≤ start_level+1，跨越必须插过渡阶段。每阶段标注类型/目标/对齐层级/过渡理由",
                "output": {"phases_sequence": [{"type": "", "name": "", "target_level": "", "transition_reason": ""}]},
                "checkpoint": True,
                "checkpoint_note": "把阶段序列展示给用户确认后再逐阶段细化",
            },
            {
                "step": 4,
                "name": "逐阶段深入细化",
                "action": "对每个阶段深入展开，不是列名式走过场：KPI（量化+验证证据）、里程碑（2-3 个带完成标准）、"
                          "任务（一次坐下可完成粒度）、jd 三件套（company/rationale 常识可写，jd/jd_status 真实数据才填）",
                "output": "完整 roadmap JSON（strategy_summary + phases，符合 roadmap.yaml output_schema）",
                "checkpoint": False,
            },
            {
                "step": 5,
                "name": "审计",
                "action": "调用 career-roadmap-auditor（独立审计角色）按 roadmap.yaml audit_checklist 逐项检查完整雏形，"
                          "输出 PASS/FAIL + 修正项；FAIL 打回步骤 4 修正，重审 ≤2 轮；仍 FAIL 则明示未通过项请用户决定",
                "output": {"verdict": "PASS/FAIL", "issues": [{"checklist_id": "", "problem": "", "fix": ""}]},
                "checkpoint": False,
            },
            {
                "step": 6,
                "name": "定稿交付",
                "action": "一次性展示全流程雏形（所有阶段/目标/KPI/里程碑/顺序理由），用户确认后调用 save_roadmap(roadmap_json)",
                "output": "save_roadmap(roadmap_json)",
                "checkpoint": True,
                "checkpoint_note": "用户确认整份路线图后才定稿保存",
            },
        ],
        "instructions": (
            "请严格按照 step_template 的 6 步分步执行，禁止一步到位。\n"
            "1. 每步必须产出该步的 output 结构后再进入下一步\n"
            "2. checkpoint=true 的步骤必须先把中间产物展示给用户确认，确认后再继续\n"
            "3. 步骤 1 用 roadmap.yaml 的 start_level_rubric 打分表判定，不是直觉\n"
            "4. 步骤 5 必须调用 career-roadmap-auditor 审计，审计通过才算定稿候选\n"
            "5. 过程中需要真实岗位数据时用 fetch_company_jobs / fetch_jd_detail 获取，"
            "拿不到就 jd 占位（pending_user_import），绝不编造\n"
            "6. 最终调用 save_roadmap(roadmap_json) 保存"
        ),
    })


_LEVEL_ORDER = {"暂不可入": 0, "小厂": 1, "中厂": 2, "大厂": 3}


def _level_rank(level: str) -> int:
    """企业层级档位转数值，用于层级连续校验。未知档位返回 -1（跳过校验）。"""
    return _LEVEL_ORDER.get(level, -1)


def _check_roadmap_hard(parsed: dict, profile) -> list[str]:
    """save_roadmap 硬校验：有数据才挡，无数据放行。

    检查：起点对齐 / 层级连续 / 届别匹配 / 必填字段。
    返回问题列表（空 = 通过）。只收集问题，由 save_roadmap 决定是否拒绝。
    """
    issues: list[str] = []
    roadmap = parsed.get("roadmap", parsed)
    phases = roadmap.get("phases", [])

    # 起点层级：优先从本次路线图自带的 start_level，否则从 gap 读
    start_level = roadmap.get("start_level", "") or (profile.gap or {}).get("start_level", "")
    start_rank = _level_rank(start_level)

    # 必填字段检查（learn 外的阶段必须有 resume_value；每阶段 KPI 必须有 metric+target）
    for phase in phases:
        phase_type = phase.get("type", "learn")
        name = phase.get("name", phase.get("id", "?"))
        if phase_type != "learn" and not phase.get("resume_value"):
            issues.append(f"阶段「{name}」类型为 {phase_type}，必须有 resume_value（如何写到简历上）")
        kpi = phase.get("kpi") or {}
        if isinstance(kpi, dict) and not (kpi.get("metric") and kpi.get("target")):
            issues.append(f"阶段「{name}」的 KPI 缺少量化指标（metric）或目标值（target）——不能是'学会'这种模糊表述")

    # 层级连续：intern 阶段 target_level ≤ start_level+1（start_level 未知时跳过）
    if start_rank >= 0:
        for phase in phases:
            phase_type = phase.get("type", "learn")
            if phase_type != "intern":
                continue
            target_level = phase.get("target_level", "")
            target_rank = _level_rank(target_level)
            if target_rank < 0:
                continue
            name = phase.get("name", phase.get("id", "?"))
            if target_rank > start_rank + 1:
                issues.append(
                    f"阶段「{name}」目标层级「{target_level}」超出起点「{start_level}」+1 的连续范围——"
                    "跨越层级必须插入过渡阶段（先进可进入的中小厂攒经历）"
                )
            elif target_rank > start_rank:
                issues.append(
                    f"阶段「{name}」目标层级「{target_level}」高于起点「{start_level}」——"
                    "请确认这是有过渡铺垫的合理进阶，而非直接跳级"
                )

    # 届别匹配：阶段 graduation_year（面向届）与用户毕业届比对
    graduation_year = (profile.who or {}).get("graduation_year", "")
    for phase in phases:
        target_year = phase.get("graduation_year", "")
        if not graduation_year or not target_year:
            continue
        name = phase.get("name", phase.get("id", "?"))
        try:
            if int(target_year) < int(graduation_year):
                issues.append(
                    f"阶段「{name}」面向届 {target_year} 早于用户毕业届 {graduation_year}——"
                    "用户投不进的届别岗位不应排在路线图里"
                )
        except (TypeError, ValueError):
            continue

    return issues


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
                    "company": "XX公司",           // 目标公司名（公开常识，可直接写）
                    "rationale": "对双非友好",     // 推荐理由
                    "jd": null,                    // 具体 JD 细节——有真实数据（抓取/导入）才填
                    "jd_status": "not_required",   // has_jd / pending_user_import / not_required
                    "confirmed": false,            // 用户已确认「先占位后补JD」
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

    注意：
    - 不要输出任何时长类字段（duration/estimated_days 等），产品不规划时间。
    - 知识光谱纪律：公司名是常识可自由写；JD 细节必须有真实数据，拿不到就 jd 置空 +
      jd_status=pending_user_import，用户确认后 confirmed 置 true。
    - 软校验：jd 有内容但无依据 / 占位未确认的阶段会在返回值中给出「依据待确认」清单，
      不会拒绝保存——请向用户确认后再定稿。
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

    # 软校验：jd 三件套约束（不拒绝保存，仅提示确认）
    warnings_list = []
    for phase in parsed.get("roadmap", parsed).get("phases", []):
        phase_type = phase.get("type", "learn")
        if phase_type == "learn":
            continue
        jd_status = phase.get("jd_status", "not_required")
        jd = phase.get("jd")
        name = phase.get("name", phase.get("id", "?"))

        if jd and jd_status != "has_jd":
            warnings_list.append(
                f"阶段「{name}」填了 JD 细节但 jd_status={jd_status}——请确认这些要求来自真实数据"
                "（抓取/导入），属实则改为 has_jd"
            )
        elif not jd and jd_status == "has_jd":
            warnings_list.append(
                f"阶段「{name}」标注 has_jd 但 jd 为空——请补上真实 JD 细节或改为占位"
            )
        elif jd_status == "pending_user_import" and not phase.get("confirmed"):
            warnings_list.append(
                f"阶段「{name}」是占位（待导入真实 JD），尚未得到用户确认——"
                "请向用户确认「先占位后补 JD」；确认后把 confirmed 置 true 再保存可消除本提示"
            )

    # 硬校验：有数据才挡，无数据放行（起点对齐/层级连续/届别匹配/必填字段）
    hard_issues = _check_roadmap_hard(parsed, profile)

    # 定稿即交付：自动生成路线图活地图 HTML（随时可重新生成）
    map_path = ""
    try:
        map_html = _render_roadmap_map(profile)
        map_path = _write_html(map_html, "career_kit_roadmap.html")
    except Exception:
        map_path = ""

    warnings_text = ""
    if warnings_list:
        warnings_text = "\n\n 依据待确认：\n" + "\n".join(f"- {w}" for w in warnings_list)

    hard_text = ""
    if hard_issues:
        hard_text = (
            "\n\n 质量硬校验（起点/层级/届别/必填）需修复：\n"
            + "\n".join(f"- {i}" for i in hard_issues)
            + "\n（已保存，但建议用 career-roadmap-auditor 审计并按修正项迭代后再定稿）"
        )

    return _json({
        "message": (
            f"路线图已保存。\n\n{report}{hard_text}{warnings_text}\n\n"
            f"路线图 HTML 已生成：{map_path}（双击即看，可随时用 export_dashboard(mode=\"roadmap\") 重新生成）\n\n"
            "接下来可以调用 generate_tasks 生成任务列表开始执行。"
        ),
        "next_steps": ["generate_tasks"],
        "context": {
            "phase": "roadmap_saved",
            "version": profile.version,
            "jd_warnings": warnings_list,
            "hard_issues": hard_issues,
        },
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
        lines.append(" 部分数据获取失败：")
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

    # 面经类详情（nowcoder 等）正文在 content 字段——此前未渲染导致「标题+公司，无正文」
    if result.get("content"):
        lines.append("### 面经内容")
        lines.append(result["content"])
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

    # 全流程概览（BUG-016）：所有阶段 + 完成状态 + 当前定位，让用户有全局地图
    roadmap = profile.plan.get("roadmap", profile.plan)
    phases = roadmap.get("phases", []) if isinstance(roadmap, dict) else []
    if phases:
        overview = []
        for idx, phase in enumerate(phases):
            phase_id = phase.get("id") or f"phase_{idx + 1}"
            phase_tasks = [t for t in profile.tasks if t.phase_id == phase_id]
            done = sum(
                1 for t in phase_tasks
                if t.status in ("completed", "skipped")
            )
            total = len(phase_tasks)
            pct = int(done / total * 100) if total else 0
            marker = "[当前]" if view and view["phase_id"] == phase_id else ("" if done == total else "·")
            overview.append(f"{marker} {phase.get('name', phase_id)}（{done}/{total}，{pct}%）")
        lines.append("## 全流程")
        lines.append("\n".join(f"  {o}" for o in overview))
        lines.append("")

    if view is None:
        lines.append("所有阶段已完成！建议回顾目标，规划下一步方向。")
        next_step = "trigger_insight(event)"
    else:
        pct = int(view["done"] / view["total"] * 100) if view["total"] else 0
        lines.append(f"## 当前阶段：{view['phase_name']}（{view['done']}/{view['total']}，{pct}%）")
        lines.append("")
        lines.append("### 接下来做")
        for t in view["next_tasks"]:
            icon = {"high": "[高]", "medium": "[中]", "low": "[低]"}.get(t.priority, "[中]")
            status_mark = "[进行中]" if t.status == "in_progress" else icon
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

    # 阶段 id → 用户可读的阶段名（提示里不能露 phase_1 这种内部 id）
    _roadmap_phases = profile.plan.get("roadmap", profile.plan).get("phases", [])
    _phase_names = {p.get("id"): p.get("name", p.get("id")) for p in _roadmap_phases}

    lines = []
    lines.append(f" 已打卡：{task.name if task else task_id}")
    if status == "skipped":
        lines[0] = f"已跳过：{task.name if task else task_id}"
    lines.append("")

    if newly_completed:
        _name = _phase_names.get(newly_completed[0], newly_completed[0])
        lines.append(f"恭喜！你完成了阶段「{_name}」的全部任务。")
        lines.append("建议调用 trigger_insight(trigger_type=\"stage_audit\") 进行阶段审计。")
        lines.append("")

    if status == "completed" and task:
        lines.append("如果完成得轻松，可以考虑加深难度或直接推进下一项——由你和用户在对话中决定。")

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
        lines.append("## 调整历史")
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

    # 目标变更检测（BUG-010）：want 是用户真实目标，变更要强告警；
    # target_jd 可能被示例/误导入污染，降级为「可核查提示」并附摘要，不再逼用户重分析
    goal_change_alert = ""
    plan_saved_at = profile.plan_saved_at
    if profile.plan.get("roadmap") and plan_saved_at:
        want_at = profile.section_updated_at.get("want", "")
        if want_at and want_at > plan_saved_at:
            goal_change_alert = (
                " 检测到用户目标（want）在路线图生成之后发生了变更。\n"
                "旧路线图可能已不适用，建议重新调用 analyze_gaps 进行分析。\n\n"
            )
        else:
            jd_at = profile.section_updated_at.get("target_jd", "")
            if jd_at and jd_at > plan_saved_at and profile.target_jd:
                jd_summary = _summarize_dict(profile.target_jd)
                goal_change_alert = (
                    f"检测到 target_jd 在路线图之后更新（{jd_summary}）。\n"
                    "若这是真实的新目标 JD，建议重新 analyze_gaps；\n"
                    "若为误导入（如示例文本），可忽略本提示，或请 LLM 用 import_jd 覆盖为真实 JD。\n\n"
                )

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
            if _has_goal(profile):
                next_step = "analyze_gaps"
            else:
                next_step = "explore_goals（尚无明确目标——先用三轴定位选定方向，再 analyze_gaps）"
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
    lines.append(f"**当前档案**：{get_active_profile_name()}")
    lines.append("")
    if goal_change_alert:
        lines.append(goal_change_alert.rstrip())
        lines.append("")
    lines.append(f"**下一步**：{next_step}")
    lines.append("")
    lines.append("### 已完成步骤")
    for step in completed_steps:
        lines.append(f"-  {step}")
    lines.append("")
    lines.append("### 任务统计")
    lines.append(f"- 总计：{total_tasks} 个")
    lines.append(f"- 已完成：{completed_tasks} 个")
    lines.append("")
    lines.append("### 工作流指南")
    lines.append("- 建档：start_session → intake(who/have/want) → finalize_profile；无目标用 explore_goals 选方向")
    lines.append("- 分析：explore_goals（无目标时）→ analyze_gaps → save_gap_analysis")
    lines.append("- 规划：generate_roadmap（按 step_template 分步：起点判定→目标拆解→阶段序列→逐阶段细化→审计→定稿）→ save_roadmap → generate_tasks")
    lines.append("- 执行：get_next_tasks → checkin_task → trigger_insight(stage_audit/event) → apply_insight")
    lines.append("- 产出：export_dashboard 生成阶段进度仪表盘")
    lines.append("")
    lines.append("节奏原则：顺序归产品，时间归用户——不为任务设定时限。")

    return "\n".join(lines)


@mcp.tool()
def export_dashboard(mode: str = "progress") -> str:
    """生成自包含 HTML（双击即可在浏览器查看，无需服务器）。

    Args:
        mode: 视图模式
            - "progress"（默认）：阶段进度仪表盘——总体/阶段进度、当前任务、能力证据、调整历史
            - "roadmap"：职业地图——完整路线图（阶段/KPI/里程碑/任务/完成标准/简历价值/
              目标公司/推荐理由/JD 依据与占位徽标）+ 每阶段执行进度 + 当前阶段高亮；
              执行中随时重新生成，永远是「最新地图」

    何时调用：
    - 用户想直观查看整体进度时调用（progress）
    - 用户想要可携带的路线图全貌时调用（roadmap）；save_roadmap 定稿时也会自动生成一份
    """
    profile = load_profile()

    if mode == "roadmap":
        html = _render_roadmap_map(profile)
        out_path = _write_html(html, "career_kit_roadmap.html")
        return (
            f"职业地图已生成：{out_path}\n\n"
            "用浏览器打开即可查看。这是一个可交互打卡应用：\n"
            "- 勾选任务即打卡，进度实时更新，状态保存在浏览器（localStorage）\n"
            "- 顶部 tab 切换阶段；「导出打卡数据」可复制打卡指令回传，由你同步到档案\n"
            "重新生成时已打卡记录不会丢失。"
        )

    if mode != "progress":
        return error_response(
            "INVALID_SECTION",
            f"mode 必须是 progress/roadmap，收到的是「{mode}」",
            {"received": mode, "valid": ["progress", "roadmap"]},
        )

    html = _render_progress_html(profile)
    out_path = _write_html(html, "career_kit_dashboard.html")

    return (
        f"仪表盘已生成：{out_path}\n\n"
        "用浏览器打开即可查看。数据为生成时刻的快照，进度更新后可重新导出。\n"
        "如需日程表，请直接在对话中为用户编写 markdown/HTML 日程文档（时间由用户自己填）。"
    )


def _write_html(html: str, filename: str) -> str:
    """把 HTML 写入临时目录并返回路径。"""
    import tempfile

    out_path = Path(tempfile.gettempdir()) / filename
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)


def _render_progress_html(profile) -> str:
    """渲染进度仪表盘 HTML（mode="progress"）。"""
    import tempfile

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
        audited = "已审计" if phase_id in profile.audited_phases else ""
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

    return html


def _render_roadmap_map(profile) -> str:
    """渲染「职业地图」HTML（mode="roadmap"）：完整路线图 + 可交互打卡。

    自包含单文件：双击打开即用，无服务器依赖。
    - 任务勾选打卡：点击 checkbox 标记完成/取消，状态持久化到浏览器 localStorage
    - 进度实时更新：阶段/总进度条随勾选联动
    - 阶段导航：顶部 tab 点击切换当前查看的阶段
    - 导出打卡数据：一键复制 JSON，粘贴回对话让 LLM 用 checkin_task 同步到档案
    重新生成时保留已打卡记录（localStorage 按档案名隔离）。
    """
    import json as _json_lib

    finished_status = ("completed", "skipped")

    roadmap = profile.plan.get("roadmap", profile.plan)
    phases = roadmap.get("phases", []) if isinstance(roadmap, dict) else []
    strategy = roadmap.get("strategy_summary", "")

    # 组装结构化数据（前端渲染 + localStorage 打卡）
    data = {
        "profile": get_active_profile_name(),
        "start_level": (profile.gap or {}).get("start_level", ""),
        "strategy": strategy,
        "phases": [],
    }
    for idx, phase in enumerate(phases):
        phase_id = phase.get("id") or f"phase_{idx + 1}"
        phase_tasks = [t for t in profile.tasks if t.phase_id == phase_id]
        done = sum(1 for t in phase_tasks if t.status in finished_status)
        total = len(phase_tasks)
        is_current = bool(profile.tasks) and phase_id == profile.tasks[0].phase_id

        jd_status = phase.get("jd_status", "not_required")
        confirmed = phase.get("confirmed", False)
        if jd_status == "has_jd":
            badge = "有 JD 依据"
            badge_cls = "ok"
        elif jd_status == "pending_user_import":
            badge = "待导入真实 JD" + ("（已确认）" if confirmed else "（待确认）")
            badge_cls = "warn"
        else:
            badge = "免 JD"
            badge_cls = ""

        jd = phase.get("jd")
        jd_text = ""
        if jd_status == "has_jd" and jd:
            if isinstance(jd, dict):
                jd_text = "；".join(f"{k}：{v}" for k, v in jd.items() if v)
            else:
                jd_text = str(jd)

        kpi = phase.get("kpi", {}) or {}
        tasks = []
        for t in phase_tasks:
            tasks.append({
                "id": t.id,
                "name": t.name,
                "desc": t.description,
                "status": t.status,
                "priority": t.priority,
                "milestone_id": t.milestone_id,
            })
        # 里程碑里的任务定义（未生成 task 时前端也能展示）
        milestone_tasks = []
        for ms in phase.get("milestones", []):
            for t in ms.get("tasks", []):
                milestone_tasks.append({
                    "name": t.get("name", ""),
                    "desc": t.get("description", ""),
                    "priority": t.get("priority", "medium"),
                })

        data["phases"].append({
            "id": phase_id,
            "name": phase.get("name", phase_id),
            "type": phase.get("type", "learn"),
            "goal": phase.get("goal", ""),
            "company": phase.get("company", ""),
            "rationale": phase.get("rationale", ""),
            "badge": badge,
            "badge_cls": badge_cls,
            "kpi_metric": kpi.get("metric", "") if isinstance(kpi, dict) else "",
            "kpi_target": kpi.get("target", "") if isinstance(kpi, dict) else "",
            "kpi_evidence": kpi.get("evidence", "") if isinstance(kpi, dict) else "",
            "resume_value": phase.get("resume_value", ""),
            "jd_text": jd_text,
            "done": done,
            "total": total,
            "is_current": is_current,
            "tasks": tasks,
            "milestone_tasks": milestone_tasks,
        })

    data_json = _json_lib.dumps(data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Career Kit 职业地图</title>
<style>
:root {{
  --bg: #f6f7fb; --card: #ffffff; --ink: #1f2430; --muted: #8a93a6;
  --line: #e6e9f0; --brand: #4a6cf7; --brand-soft: #eef1fe;
  --ok: #22a06b; --ok-soft: #e8f7f0; --warn: #b26a00; --warn-soft: #fff4e0;
  --radius: 14px; --shadow: 0 1px 3px rgba(31,36,48,.06), 0 4px 16px rgba(31,36,48,.05);
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
       background: var(--bg); color: var(--ink); line-height: 1.6; }}
.wrap {{ max-width: 980px; margin: 0 auto; padding: 28px 20px 60px; }}
header {{ display: flex; align-items: flex-end; justify-content: space-between;
          gap: 16px; flex-wrap: wrap; margin-bottom: 6px; }}
h1 {{ font-size: 24px; letter-spacing: .3px; }}
.meta {{ color: var(--muted); font-size: 12.5px; }}
.start {{ margin: 6px 0 18px; color: var(--muted); font-size: 13.5px; }}
.start b {{ color: var(--brand); }}
.strategy {{ background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
             padding: 14px 16px; margin: 12px 0 22px; color: #4a5160; font-size: 14px;
             box-shadow: var(--shadow); }}
/* 总进度 */
.overview {{ display: flex; gap: 18px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }}
.ring {{ --p: 0; width: 74px; height: 74px; border-radius: 50%;
         background: conic-gradient(var(--brand) calc(var(--p)*1%), #e6e9f0 0);
         display: grid; place-items: center; }}
.ring div {{ width: 58px; height: 58px; border-radius: 50%; background: var(--card);
             display: grid; place-items: center; font-weight: 700; font-size: 15px; color: var(--brand); }}
.overview-txt {{ font-size: 13.5px; color: var(--muted); }}
.overview-txt b {{ color: var(--ink); font-size: 15px; }}
/* 阶段导航 */
.tabs {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 18px 0 16px; }}
.tab {{ padding: 8px 16px; border: 1px solid var(--line); background: var(--card);
        border-radius: 999px; font-size: 13.5px; cursor: pointer; color: var(--muted);
        transition: all .15s; }}
.tab:hover {{ border-color: var(--brand); color: var(--brand); }}
.tab.active {{ background: var(--brand); border-color: var(--brand); color: #fff; }}
.tab .tab-pct {{ margin-left: 6px; font-size: 12px; opacity: .8; }}
/* 阶段卡片 */
.card {{ background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
         padding: 20px 22px; margin-bottom: 16px; box-shadow: var(--shadow);
         display: none; }}
.card.active {{ display: block; }}
.card-head {{ display: flex; justify-content: space-between; align-items: flex-start;
              gap: 12px; flex-wrap: wrap; margin-bottom: 4px; }}
.card-title {{ font-size: 17px; font-weight: 700; }}
.type-pill {{ font-size: 11.5px; color: var(--muted); border: 1px solid var(--line);
             border-radius: 6px; padding: 1px 7px; margin-left: 8px; vertical-align: 2px; }}
.badge {{ display: inline-block; font-size: 11px; color: #666; background: #eee;
          border-radius: 8px; padding: 1px 7px; margin-left: 4px; }}
.badge.ok {{ color: var(--ok); background: var(--ok-soft); }}
.badge.warn {{ color: var(--warn); background: var(--warn-soft); }}
.cur-tag {{ color: var(--brand); font-size: 12px; margin-left: 8px; }}
.bar {{ background: #eef0f6; border-radius: 999px; height: 8px; overflow: hidden; margin: 10px 0 14px; }}
.fill {{ background: linear-gradient(90deg, var(--brand), #6f8bff); height: 100%; width: 0; transition: width .3s; }}
.done-txt {{ color: var(--muted); font-size: 12.5px; }}
.goal {{ color: #4a5160; font-size: 13.5px; margin: 6px 0; }}
.kpi {{ color: #5a6270; font-size: 13px; margin: 2px 0; }}
.resume {{ color: var(--ok); font-size: 13px; margin: 2px 0; }}
.jd {{ color: #455a64; background: #f4f7f8; padding: 8px 12px; border-radius: 8px;
      font-size: 12.5px; margin: 8px 0; }}
.company {{ margin: 6px 0 2px; font-size: 13px; font-weight: 600; }}
/* 任务列表 */
.tasks {{ margin-top: 12px; border-top: 1px dashed var(--line); padding-top: 6px; }}
.task {{ display: flex; align-items: flex-start; gap: 10px; padding: 9px 4px;
         border-radius: 8px; cursor: pointer; }}
.task:hover {{ background: var(--brand-soft); }}
.task input {{ width: 18px; height: 18px; margin-top: 2px; accent-color: var(--brand); cursor: pointer; }}
.task-name {{ flex: 1; font-size: 13.5px; }}
.task-name.done {{ text-decoration: line-through; color: var(--muted); }}
.task-meta {{ color: var(--muted); font-size: 12px; }}
.ms {{ font-size: 12px; color: var(--muted); margin-top: 8px; font-weight: 600; }}
.pr {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
.pr-high {{ background: #e5484d; }} .pr-medium {{ background: #f5a524; }} .pr-low {{ background: #22a06b; }}
.empty {{ color: var(--muted); font-size: 13px; padding: 8px 0; }}
/* 底部操作 */
.actions {{ position: sticky; bottom: 16px; display: flex; gap: 10px; justify-content: flex-end;
            margin-top: 18px; }}
.btn {{ padding: 9px 16px; border-radius: 10px; border: 1px solid var(--line);
        background: var(--card); font-size: 13px; cursor: pointer; color: var(--ink); }}
.btn.primary {{ background: var(--brand); border-color: var(--brand); color: #fff; }}
.btn:hover {{ opacity: .9; }}
.footer {{ text-align: center; color: var(--muted); font-size: 12px; margin-top: 30px; }}
.toast {{ position: fixed; left: 50%; bottom: 70px; transform: translateX(-50%);
         background: #1f2430; color: #fff; padding: 9px 18px; border-radius: 10px;
         font-size: 13px; opacity: 0; pointer-events: none; transition: opacity .25s; }}
.toast.show {{ opacity: 1; }}
@media (max-width: 640px) {{ .wrap {{ padding: 16px 12px 60px; }} }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Career Kit 职业地图</h1>
    <span class="meta">生成于 {datetime.now().strftime("%Y-%m-%d %H:%M")} · 路线图 v{profile.version}</span>
  </header>

  <p class="start">起点层级：<b id="start-level">—</b>（差距分析产出，路线图按此对齐）</p>

  <div class="strategy" id="strategy">—</div>

  <div class="overview">
    <div class="ring" id="ring"><div id="ring-pct">0%</div></div>
    <div class="overview-txt">
      <div>总进度：<b id="total-pct">0%</b></div>
      <div id="total-done">已完成 0 / 0 个任务</div>
    </div>
  </div>

  <div class="tabs" id="tabs"></div>

  <div id="cards"></div>

  <div class="actions">
    <button class="btn" id="export-btn">导出打卡数据</button>
    <button class="btn" id="reset-btn">重置本地打卡</button>
  </div>

  <p class="footer">顺序归产品，时间归用户。勾选任务即本地打卡（浏览器保存）；点「导出打卡数据」把打卡结果粘贴回对话，即可同步到档案。</p>
</div>
<div class="toast" id="toast"></div>

<script type="application/json" id="career-data">{data_json}</script>
<script>
(function () {{
  'use strict';
  var DATA = JSON.parse(document.getElementById('career-data').textContent);
  var KEY = 'career-kit-checkins-' + DATA.profile;

  function loadCheckins() {{
    try {{ return JSON.parse(localStorage.getItem(KEY) || '{{}}'); }}
    catch (e) {{ return {{}}; }}
  }}
  function saveCheckins(c) {{ localStorage.setItem(KEY, JSON.stringify(c)); }}

  var checkins = loadCheckins();

  // 阶段初始状态：服务端已有 completed/skipped 的任务视为已打卡
  var phases = DATA.phases.map(function (ph) {{
    var tasks = ph.tasks.map(function (t) {{
      var serverDone = (t.status === 'completed' || t.status === 'skipped');
      var base = serverDone ? 'done' : 'open';
      var st = checkins[t.id] || base;
      return {{ id: t.id, name: t.name, desc: t.desc, priority: t.priority,
                 milestone_id: t.milestone_id, state: st, __server_done: serverDone }};
    }});
    return {{
      id: ph.id, name: ph.name, type: ph.type, goal: ph.goal,
      company: ph.company, rationale: ph.rationale, badge: ph.badge, badge_cls: ph.badge_cls,
      kpi_metric: ph.kpi_metric, kpi_target: ph.kpi_target, kpi_evidence: ph.kpi_evidence,
      resume_value: ph.resume_value, jd_text: ph.jd_text,
      is_current: ph.is_current, tasks: tasks, milestone_tasks: ph.milestone_tasks,
      done: 0, total: tasks.length
    }};
  }});

  function render() {{
    var tabsEl = document.getElementById('tabs');
    var cardsEl = document.getElementById('cards');
    tabsEl.innerHTML = '';
    cardsEl.innerHTML = '';

    var totalDone = 0, totalAll = 0;
    phases.forEach(function (ph) {{
      var done = ph.tasks.filter(function (t) {{ return t.state === 'done'; }}).length;
      ph.done = done;
      totalDone += done; totalAll += ph.total;
      var pct = ph.total ? Math.round(done / ph.total * 100) : 0;
      ph.pct = pct;

      var tab = document.createElement('div');
      tab.className = 'tab' + (ph.is_current ? ' active' : '');
      tab.dataset.id = ph.id;
      tab.innerHTML = ph.name + '<span class="tab-pct">' + done + '/' + ph.total + ' · ' + pct + '%</span>';
      tabsEl.appendChild(tab);

      var badge = ph.badge ? '<span class="badge ' + ph.badge_cls + '">' + ph.badge + '</span>' : '';
      var cur = ph.is_current ? '<span class="cur-tag">[当前]</span>' : '';
      var company = ph.company ? '<div class="company">' + ph.company
        + (ph.rationale ? ' <span class="meta">— ' + ph.rationale + '</span>' : '') + '</div>' : '';
      var kpi = ph.kpi_metric
        ? '<div class="kpi">KPI：' + ph.kpi_metric + ' → ' + ph.kpi_target
          + (ph.kpi_evidence ? '（验证：' + ph.kpi_evidence + '）' : '') + '</div>' : '';
      var resume = ph.resume_value ? '<div class="resume">简历价值：' + ph.resume_value + '</div>' : '';
      var jd = ph.jd_text ? '<div class="jd">' + ph.jd_text.slice(0, 400) + '</div>' : '';

      var tasksHtml = '';
      if (ph.tasks.length) {{
        var lastMs = null;
        ph.tasks.forEach(function (t) {{
          var msLabel = '';
          if (t.milestone_id && t.milestone_id !== lastMs) {{
            lastMs = t.milestone_id;
            msLabel = '<div class="ms">里程碑：' + t.milestone_id.replace(/.*_ms_/, 'M') + '</div>';
          }}
          var pr = {{ high: 'pr-high', medium: 'pr-medium', low: 'pr-low' }}[t.priority] || 'pr-medium';
          tasksHtml += msLabel
            + '<label class="task">'
            + '<input type="checkbox" data-id="' + t.id + '"' + (t.state === 'done' ? ' checked' : '') + '>'
            + '<span class="task-name' + (t.state === 'done' ? ' done' : '') + '">'
            + '<span class="pr ' + pr + '"></span>' + t.name + '</span>'
            + '<span class="task-meta">' + t.id + '</span>'
            + '</label>';
        }});
      }} else if (ph.milestone_tasks.length) {{
        tasksHtml = '<div class="empty">里程碑已规划（任务列表生成后即可打卡）</div>';
      }} else {{
        tasksHtml = '<div class="empty">暂无任务</div>';
      }}

      var card = document.createElement('div');
      card.className = 'card' + (ph.is_current ? ' active' : '');
      card.dataset.id = ph.id;
      card.innerHTML =
        '<div class="card-head"><span class="card-title">' + ph.name
          + '<span class="type-pill">' + ph.type + '</span>' + badge + cur + '</span>'
          + '<span class="done-txt">' + done + '/' + ph.total + ' · ' + pct + '%</span></div>'
        + '<div class="bar"><div class="fill" style="width:' + pct + '%"></div></div>'
        + company
        + (ph.goal ? '<div class="goal">' + ph.goal + '</div>' : '')
        + kpi + resume + jd
        + '<div class="tasks">' + tasksHtml + '</div>';
      cardsEl.appendChild(card);
    }});

    var totalPct = totalAll ? Math.round(totalDone / totalAll * 100) : 0;
    document.getElementById('ring').style.setProperty('--p', totalPct);
    document.getElementById('ring-pct').textContent = totalPct + '%';
    document.getElementById('total-pct').textContent = totalPct + '%';
    document.getElementById('total-done').textContent = '已完成 ' + totalDone + ' / ' + totalAll + ' 个任务';
  }}

  function toast(msg) {{
    var t = document.getElementById('toast');
    t.textContent = msg; t.classList.add('show');
    setTimeout(function () {{ t.classList.remove('show'); }}, 1800);
  }}

  // 阶段导航
  document.getElementById('tabs').addEventListener('click', function (e) {{
    var tab = e.target.closest('.tab'); if (!tab) return;
    document.querySelectorAll('.tab').forEach(function (x) {{ x.classList.remove('active'); }});
    document.querySelectorAll('.card').forEach(function (x) {{ x.classList.remove('active'); }});
    tab.classList.add('active');
    document.querySelector('.card[data-id="' + tab.dataset.id + '"]').classList.add('active');
  }});

  // 任务勾选打卡
  document.getElementById('cards').addEventListener('change', function (e) {{
    var cb = e.target;
    if (!cb.matches('input[type=checkbox]')) return;
    var id = cb.dataset.id;
    phases.forEach(function (ph) {{
      ph.tasks.forEach(function (t) {{ if (t.id === id) t.state = cb.checked ? 'done' : 'open'; }});
    }});
    checkins[id] = cb.checked ? 'done' : 'open';
    saveCheckins(checkins);
    render();
    toast(cb.checked ? '已打卡：' + id : '已取消打卡：' + id);
  }});

  // 导出打卡数据（回传 LLM 同步档案）
  document.getElementById('export-btn').addEventListener('click', function () {{
    var rows = [];
    phases.forEach(function (ph) {{
      ph.tasks.forEach(function (t) {{
        if (t.state === 'done') rows.push('checkin_task(task_id="' + t.id + '", status="completed")');
      }});
    }});
    var text = rows.length ? rows.join('\\n') : '（暂无打卡记录）';
    var pre = document.createElement('textarea');
    pre.value = text; document.body.appendChild(pre); pre.select();
    try {{ document.execCommand('copy'); toast('已复制 ' + rows.length + ' 条打卡指令'); }}
    catch (err) {{ prompt('复制以下打卡指令回传对话：', text); }}
    pre.remove();
  }});

  // 重置本地打卡
  document.getElementById('reset-btn').addEventListener('click', function () {{
    if (!confirm('确认清除本浏览器的打卡记录？（仅本地，不影响档案）')) return;
    checkins = {{}};
    phases.forEach(function (ph) {{
      ph.tasks.forEach(function (t) {{
        // 只重置用户本地勾选，服务端已完成的（初始 done）保持完成
        if (t.state === 'done' && !t.__server_done) t.state = 'open';
      }});
    }});
    saveCheckins(checkins); render(); toast('已重置本地打卡');
  }});

  render();
}})();
</script>
</body></html>"""


def main():
    mcp.run()


if __name__ == "__main__":
    main()
