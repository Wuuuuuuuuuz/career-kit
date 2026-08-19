"""Career Kit MCP 服务器——入口。"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("career-kit")


@mcp.tool()
def start_session() -> str:
    """初始化新的职业规划会话。返回欢迎信息，询问用户当前状况。"""
    return (
        "欢迎使用 Career Kit，让我们来规划你的职业路线。\n\n"
        "先告诉我你现在的状态——在校生、在职、待业、还是想转行？"
    )


@mcp.tool()
def intake(section: str, data: str) -> str:
    """逐步填充档案信息。

    Args:
        section: 填充到哪个 section，可选 who / have / want
        data: 用户提供的信息，自然语言
    """
    # TODO: 解析 data，合并到档案对应 section
    return f"已记录到「{section}」：{data}"


@mcp.tool()
def finalize_profile() -> str:
    """确认档案信息完整，生成摘要，解锁分析工具。"""
    # TODO: 从 who/have/want 生成 summary
    return "档案已确认，可以开始分析差距了。"


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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
