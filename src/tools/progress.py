"""进度追踪——记录完成情况，调整计划。"""

from ..models import CareerProfile


def track(profile: CareerProfile, report: str) -> dict:
    """记录进度，判断是否需要调整计划。

    Args:
        profile: 当前职业档案
        report: 用户完成的内容

    Returns:
        包含 log_entry 和 adjustments 的字典
    """
    return {
        "log_entry": {
            "date": profile.updated_at,
            "report": report,
        },
        "adjustments": None,
    }
