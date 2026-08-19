"""Career Kit MCP 服务器——入口。"""

from mcp.server.fastmcp import FastMCP

from .tools.plan_importer import compare_plans, format_diff_report, parse_plan_file
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
def analyze_gaps() -> str:
    """对比现状（have）与目标（want），搜索市场数据，写入差距分析。"""
    # TODO: 读取档案，web search，写入 gap section
    return "差距分析完成，接下来运行 generate_roadmap 生成路线图。"


@mcp.tool()
def generate_roadmap() -> str:
    """基于差距分析生成分阶段职业路线图，考虑用户可用时间和截止日期。"""
    # TODO: 读取 gap + 可用时间，写入 plan section
    return "路线图已生成，运行 generate_schedule 获取具体日程。"


@mcp.tool()
def generate_schedule(scope: str = "this_week") -> str:
    """将路线图拆解为具体日程。

    Args:
        scope: 范围，可选 today / this_week / this_month，或某个阶段 id
    """
    # TODO: 读取 plan，输出日程，可选导出 ICS
    return f"「{scope}」的日程已生成。"


@mcp.tool()
def track_progress(report: str) -> str:
    """记录进度，自动调整后续计划。

    Args:
        report: 用户完成的内容，自然语言
    """
    # TODO: 更新 plan，写入日志，重新计算日程
    return f"进度已记录：{report}"


@mcp.tool()
def search_market(query: str) -> str:
    """搜索就业市场信息。

    Args:
        query: 搜索内容——岗位名称、公司、薪资、面试经验等
    """
    # TODO: web search，格式化结果
    return f"市场搜索结果：{query}"


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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
