"""差距分析——对比 have 与 want，拉取市场数据。"""

from ..models import CareerProfile


def analyze(profile: CareerProfile) -> dict:
    """分析现状与目标之间的差距。

    返回写入 profile.gap 的字典。
    这里只提供结构，具体分析由 LLM 完成。
    """
    return {
        "skill_gaps": [],       # 技能差距
        "experience_gaps": [],  # 经历差距
        "market_context": "",   # 市场背景
        "priority_order": [],   # 优先级排序
        "raw_analysis": "",     # 原始分析文本
    }
