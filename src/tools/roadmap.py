"""路线图生成——把差距分析变成分阶段计划。"""

from ..models import CareerProfile


def generate(profile: CareerProfile) -> dict:
    """基于差距分析生成分阶段路线图。

    返回写入 profile.plan 的字典。
    结构故意松散——阶段粒度、任务拆分、策略都由 LLM 根据用户情况决定。
    """
    return {
        "phases": [],               # 阶段列表
        "strategy_notes": "",       # 策略说明
        "total_estimated_weeks": 0, # 预估总周数
    }
