"""档案管理——初始化会话、逐步填充、确认档案、多档案切换。

多档案机制：
- 档案文件为 PROFILE_DIR/{name}.json，名称任意（默认 "default"）。
- 当前活跃档案记录在 PROFILE_DIR/.active_profile，无记录时回退 "default"。
- 不传 name 的所有读写操作都作用于当前活跃档案；
  显式传 name 的操作不受影响（测试/切换场景用）。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..models import CareerProfile
from ..paths import PROFILE_DIR

ACTIVE_PROFILE_FILE = ".active_profile"


def get_active_profile_name() -> str:
    """读取当前活跃档案名，未设置时回退 "default"。"""
    active_file = PROFILE_DIR / ACTIVE_PROFILE_FILE
    try:
        name = active_file.read_text(encoding="utf-8").strip()
        if name:
            return name
    except OSError:
        pass
    return "default"


def set_active_profile_name(name: str) -> None:
    """把指定档案设为当前活跃档案。"""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    (PROFILE_DIR / ACTIVE_PROFILE_FILE).write_text(name, encoding="utf-8")


def list_profiles() -> list[dict[str, Any]]:
    """列出所有档案（含元信息），不含 .active_profile 等非档案文件。"""
    if not PROFILE_DIR.exists():
        return []
    active = get_active_profile_name()
    profiles = []
    for path in sorted(PROFILE_DIR.glob("*.json")):
        name = path.stem
        info: dict[str, Any] = {"name": name, "is_active": name == active}
        try:
            profile = CareerProfile.model_validate_json(path.read_text(encoding="utf-8"))
            info["version"] = profile.version
            info["updated_at"] = profile.updated_at
            who = profile.who or {}
            info["person"] = who.get("name") or who.get("raw", "")
            want = profile.want or {}
            info["target"] = want.get("target_role") or want.get("direction") or want.get("raw", "")
            info["has_plan"] = bool(profile.plan.get("roadmap") or profile.plan.get("phases"))
        except Exception:
            info["version"] = 0
            info["updated_at"] = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        profiles.append(info)
    return profiles


def delete_profile(name: str) -> bool:
    """删除指定档案。当前活跃档案禁止删除（防止误删正在使用的数据）。"""
    if name == get_active_profile_name():
        return False
    path = PROFILE_DIR / f"{name}.json"
    if not path.exists():
        return False
    path.unlink()
    return True


def load_profile(name: str | None = None) -> CareerProfile:
    """从本地加载档案，不存在则返回空档案。

    name 为 None 时加载当前活跃档案（未设置则回退 "default"）。
    """
    if name is None:
        name = get_active_profile_name()
    path = PROFILE_DIR / f"{name}.json"
    if path.exists():
        return CareerProfile.model_validate_json(path.read_text(encoding="utf-8"))
    return CareerProfile()


def save_profile(profile: CareerProfile, name: str | None = None) -> None:
    """保存档案到本地。name 为 None 时保存到当前活跃档案。"""
    if name is None:
        name = get_active_profile_name()
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILE_DIR / f"{name}.json"
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")


def merge_section(
    section: str, data: str, name: str | None = None
) -> CareerProfile:
    """将 data 合并到档案的指定 section 并保存。

    data 尝试按 JSON 解析；如果不是合法 JSON，则存为 {"raw": data}。

    Args:
        section: 目标 section（who/have/want/gap/plan）。
        data: LLM 传来的字符串，期望是 JSON。
        name: 档案名称；None 表示当前活跃档案（默认 "default"）。

    Returns:
        更新后的档案。
    """
    profile = load_profile(name)

    try:
        parsed: dict[str, Any] = json.loads(data)
        if not isinstance(parsed, dict):
            parsed = {"raw": data}
    except (json.JSONDecodeError, TypeError):
        parsed = {"raw": data}

    profile.merge(section, parsed)
    save_profile(profile, name)
    return profile


def save_plan_snapshot(
    source: str, import_file: str | None = None, name: str | None = None
) -> CareerProfile:
    """保存当前 plan 到版本历史。

    Args:
        source: 来源标识（"generated" | "imported" | "manual"）
        import_file: 如果是导入的，记录文件路径
        name: 档案名称；None 表示当前活跃档案（默认 "default"）

    Returns:
        更新后的档案。
    """
    profile = load_profile(name)
    profile.save_plan_snapshot(source, import_file)
    save_profile(profile, name)
    return profile
