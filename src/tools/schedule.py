"""日程生成——把路线图拆解为每日/每周任务。"""

from ..models import CareerProfile


def generate_schedule(profile: CareerProfile, scope: str = "this_week") -> str:
    """将路线图拆解为具体日程。

    Args:
        profile: 包含 plan 数据的职业档案
        scope: 范围——today / this_week / this_month，或某个阶段 id

    Returns:
        Markdown 格式的日程表
    """
    # TODO: 读取 plan.phases，按可用时间分配任务
    return f"# 日程：{scope}\n\n（待实现）"
