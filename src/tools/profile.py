"""档案管理——初始化会话、逐步填充、确认档案。"""

from pathlib import Path

from ..models import CareerProfile

PROFILE_DIR = Path.home() / ".career-kit"


def load_profile(name: str = "default") -> CareerProfile:
    """从本地加载档案，不存在则返回空档案。"""
    path = PROFILE_DIR / f"{name}.json"
    if path.exists():
        return CareerProfile.model_validate_json(path.read_text(encoding="utf-8"))
    return CareerProfile()


def save_profile(profile: CareerProfile, name: str = "default") -> None:
    """保存档案到本地。"""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILE_DIR / f"{name}.json"
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
