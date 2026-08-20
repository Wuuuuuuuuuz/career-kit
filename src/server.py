"""Career Kit MCP 服务器——入口。"""

from mcp.server.fastmcp import FastMCP

from .tools.gap_analyzer import (
    build_gap_analysis_prompt,
    build_sop_analysis_prompt,
    format_gap_report,
    parse_gap_analysis,
)
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
from .tools.roadmap import build_roadmap_prompt, format_roadmap, parse_roadmap
from .tools.schedule import (
    build_schedule_prompt,
    format_schedule,
    generate_ics,
    parse_schedule,
)
from .tools.profile import (
    get_plan_history,
    load_profile,
    merge_section,
    restore_plan_version,
    save_plan_snapshot,
    save_profile,
)
from .tools.resume_parser import extract_text
from .tools.session import get_welcome_message
from .scrapers import list_scrapers, search_company_jobs, get_job_detail

mcp = FastMCP("career-kit")


@mcp.tool()
def start_session() -> str:
    """初始化新的职业规划会话。返回欢迎信息，询问用户当前状况。"""
    return get_welcome_message()


@mcp.tool()
def parse_resume(file_path: str) -> str:
    """解析简历文件，提取文本内容。支持 PDF、DOCX、Markdown、TXT 格式。

    Args:
        file_path: 简历文件的绝对路径
    """
    try:
        text = extract_text(file_path)
    except FileNotFoundError as e:
        return f"错误：{e}"
    except ValueError as e:
        return f"错误：{e}"

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

    Args:
        section: 填充到哪个 section，可选 who / have / want / plan
        data: 用户提供的信息，期望是 JSON 字符串
    """
    if section not in ("who", "have", "want", "plan"):
        return f"错误：section 必须是 who/have/want/plan，收到的是「{section}」"

    profile = merge_section(section, data)
    return f"已记录到「{section}」。当前档案版本：v{profile.version}"


@mcp.tool()
def finalize_profile() -> str:
    """确认档案信息完整，生成摘要，解锁分析工具。"""
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
    import json
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
        return f"错误：{e}"
    except ValueError as e:
        return f"错误：{e}"

    return (
        f"--- JD CONTENT ---\n{text}\n--- END ---\n\n"
        "根据以上 JD 内容，请调用 import_jd 工具导入：\n"
        '示例：import_jd(jd_text=\'{"company":"字节跳动","role":"AI Agent 工程师","requirements":[...]}\'）'
    )


@mcp.tool()
def analyze_gaps() -> str:
    """对比现状（have）与目标（want/target_jd），输出差距分析。

    使用 SOP 驱动的 RAG 模式：
    1. 加载 SOP 配置（简历过筛 + 面试通过）
    2. 按步骤执行：构建画像 → 检索数据 → 差异分析 → 构建建议
    3. 返回完整 prompt 让 LLM 分析

    中间步骤会展示给用户，让用户看到分析过程。
    """
    profile = load_profile()

    if not profile.have and not profile.want:
        return "错误：档案中缺少 have（现状）或 want（目标）信息。请先调用 intake 填充。"

    # SOP 驱动的分析
    prompt, metadata = build_sop_analysis_prompt(profile)

    # 构建中间输出（让用户看到 SOP 步骤）
    steps_info = []
    if metadata.get("resume_sop"):
        steps_info.append(f"📋 简历过筛 SOP（v{metadata['resume_sop']['version']}）")
        for step in metadata["resume_sop"]["steps"]:
            steps_info.append(f"  ✓ {step['name']}")

    if metadata.get("interview_sop"):
        steps_info.append(f"🎯 面试通过 SOP（v{metadata['interview_sop']['version']}）")
        for step in metadata["interview_sop"]["steps"]:
            steps_info.append(f"  ✓ {step['name']}")

    steps_text = "\n".join(steps_info)

    return (
        f"【差距分析任务】\n\n"
        f"已执行以下 SOP 步骤：\n{steps_text}\n\n"
        f"{'=' * 50}\n\n"
        f"{prompt}\n\n"
        f"{'=' * 50}\n\n"
        "请基于以上信息进行分析，然后调用 save_gap_analysis(gap_json) 保存结果。"
    )


@mcp.tool()
def save_gap_analysis(gap_json: str) -> str:
    """保存差距分析结果。

    Args:
        gap_json: 差距分析的 JSON 字符串
    """
    import json

    try:
        gap_data = json.loads(gap_json)
        if not isinstance(gap_data, dict):
            return "错误：差距分析必须是 JSON 对象格式"
    except json.JSONDecodeError:
        return "错误：无法解析差距分析 JSON"

    profile = load_profile()
    profile.gap = gap_data
    profile.touch()
    save_profile(profile)

    # 格式化报告
    report = format_gap_report(gap_data)

    return (
        f"差距分析已保存。\n\n{report}\n\n"
        "接下来可以调用 generate_roadmap 生成路线图。"
    )


@mcp.tool()
def generate_roadmap() -> str:
    """基于差距分析生成分阶段职业路线图。

    使用 SOP 驱动：
    1. 从差距分析中提取需要弥补的技能和经验
    2. LLM 动态设计阶段（learn/project/intern/research）
    3. 每阶段设定量化 KPI + 简历价值
    4. 拆成里程碑和每日任务

    必须先完成差距分析（analyze_gaps + save_gap_analysis）。
    """
    profile = load_profile()

    if not profile.gap:
        return "错误：请先调用 analyze_gaps 完成差距分析，再生成路线图。"

    # SOP 驱动的路线图生成
    prompt, metadata = build_roadmap_prompt(profile)

    # 构建中间输出
    steps_info = []
    if metadata.get("roadmap_sop"):
        steps_info.append(f"🗺️ 路线图 SOP（v{metadata['roadmap_sop']['version']}）")
        for step in metadata["roadmap_sop"]["steps"]:
            steps_info.append(f"  ✓ {step['name']}")

    steps_text = "\n".join(steps_info)

    return (
        f"【路线图生成任务】\n\n"
        f"已执行以下 SOP 步骤：\n{steps_text}\n\n"
        f"{'=' * 50}\n\n"
        f"{prompt}\n\n"
        f"{'=' * 50}\n\n"
        "请基于以上信息生成路线图，然后调用 save_roadmap(roadmap_json) 保存结果。"
    )


@mcp.tool()
def save_roadmap(roadmap_json: str) -> str:
    """保存路线图到档案。

    Args:
        roadmap_json: 路线图的 JSON 字符串
    """
    import json

    try:
        roadmap_data = json.loads(roadmap_json)
        if not isinstance(roadmap_data, dict):
            return "错误：路线图必须是 JSON 对象格式"
    except json.JSONDecodeError:
        return "错误：无法解析路线图 JSON"

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

    return (
        f"路线图已保存。\n\n{report}\n\n"
        "接下来可以调用 generate_schedule 获取具体日程。"
    )


@mcp.tool()
def generate_schedule(scope: str = "this_week") -> str:
    """将路线图拆解为每日时间块日程表。

    特点：
    - 时间块（time-block）排程，每天不超过 8 小时
    - 高优先级任务排前面
    - 每隔 3 天安排复习日（间隔复习）
    - 支持导出 ICS 日历文件

    Args:
        scope: 范围，可选 today / this_week / this_month

    必须先生成路线图（generate_roadmap + save_roadmap）。
    """
    profile = load_profile()

    if not profile.plan or not profile.plan.get("roadmap"):
        return "错误：请先调用 generate_roadmap 生成路线图，再生成日程。"

    # SOP 驱动的日程生成
    prompt, metadata = build_schedule_prompt(profile, scope)

    # 构建中间输出
    steps_info = []
    if metadata.get("schedule_sop"):
        steps_info.append(f"📅 日程 SOP（v{metadata['schedule_sop']['version']}）")
        for step in metadata["schedule_sop"]["steps"]:
            steps_info.append(f"  ✓ {step['name']}")

    steps_text = "\n".join(steps_info)

    return (
        f"【日程生成任务】\n\n"
        f"范围：{scope}\n"
        f"已执行以下 SOP 步骤：\n{steps_text}\n\n"
        f"{'=' * 50}\n\n"
        f"{prompt}\n\n"
        f"{'=' * 50}\n\n"
        "请基于以上信息生成日程表，然后调用 save_schedule(schedule_json) 保存结果。\n"
        "如需导出 ICS 日历文件，请在保存后调用 export_ics。"
    )


@mcp.tool()
def save_schedule(schedule_json: str) -> str:
    """保存日程表到档案。

    Args:
        schedule_json: 日程表的 JSON 字符串
    """
    import json

    try:
        schedule_data = json.loads(schedule_json)
        if not isinstance(schedule_data, dict):
            return "错误：日程表必须是 JSON 对象格式"
    except json.JSONDecodeError:
        return "错误：无法解析日程表 JSON"

    profile = load_profile()

    # 解析并写入 plan
    parsed = parse_schedule(json.dumps(schedule_data, ensure_ascii=False))
    profile.plan["schedule"] = parsed.get("schedule", parsed)
    profile.touch()
    save_profile(profile)

    # 格式化报告
    report = format_schedule(parsed)

    return (
        f"日程表已保存。\n\n{report}\n\n"
        "如需导出 ICS 日历文件，请调用 export_ics。\n"
        "开始执行后，请调用 track_progress 记录进度。"
    )


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
        return "错误：请先调用 generate_schedule 生成日程。"

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

    签到模式（借鉴 Plan Tracker MCP）：
    - 完成了什么任务
    - 花了多少时间
    - 遇到什么阻碍
    - 当前士气

    支持：
    - 偏差分析：实际进度 vs 计划进度
    - 自动重排：落后时建议调整方案
    - 进度可视化：进度条 + 里程碑状态

    Args:
        report: 用户的进度汇报（自然语言）
    """
    profile = load_profile()

    if not profile.plan:
        return "错误：请先生成路线图和日程。"

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
    import json

    try:
        checkin_data = json.loads(checkin_json)
        if not isinstance(checkin_data, dict):
            return "错误：签到数据必须是 JSON 对象格式"
    except json.JSONDecodeError:
        return "错误：无法解析签到 JSON"

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

    搜索类型自动推断：
    - 面试相关 → 搜索面经
    - 薪资相关 → 搜索薪资数据
    - JD 相关 → 搜索岗位要求
    - 其他 → 市场趋势

    数据来源（按优先级）：
    1. 本地知识库（dev/knowledge/market/）
    2. LLM 知识（兜底）
    3. Web Search API（TODO: 后续接入）

    Args:
        query: 搜索内容——岗位名称、公司、薪资、面试经验等
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
        return f"错误：{e}"
    except ValueError as e:
        return f"错误：{e}"

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
    import json

    profile = load_profile()

    if not profile.plan:
        return "当前没有已有计划，无需对比。请直接调用 intake 填充 plan section。"

    try:
        new_plan_dict = json.loads(new_plan)
        if not isinstance(new_plan_dict, dict):
            return "错误：新计划必须是 JSON 对象格式"
    except json.JSONDecodeError:
        return "错误：无法解析新计划 JSON"

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
    import json

    try:
        new_plan_dict = json.loads(new_plan)
        if not isinstance(new_plan_dict, dict):
            return "错误：新计划必须是 JSON 对象格式"
    except json.JSONDecodeError:
        return "错误：无法解析新计划 JSON"

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
    import json

    try:
        new_plan_dict = json.loads(new_plan)
        if not isinstance(new_plan_dict, dict):
            return "错误：新计划必须是 JSON 对象格式"
    except json.JSONDecodeError:
        return "错误：无法解析新计划 JSON"

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
        return f"错误：{e}"


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

    Args:
        company: 企业 ID（通过 list_company_jobs 获取）
        params: 搜索参数 JSON 字符串（各企业支持的参数不同）
    """
    import json

    try:
        params_dict = json.loads(params) if params else {}
    except json.JSONDecodeError:
        return "错误：params 必须是合法的 JSON 字符串"

    result = search_company_jobs(company, **params_dict)

    if result.get("error"):
        available = result.get("available", [])
        avail_str = f"\n可用企业：{', '.join(available)}" if available else ""
        return f"错误：{result['error']}{avail_str}"

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
        return f"错误：{result['error']}"

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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
