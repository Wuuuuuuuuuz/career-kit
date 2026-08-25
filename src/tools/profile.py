"""档案管理——初始化会话、逐步填充、确认档案。"""

from __future__ import annotations

import json
from typing import Any

from ..models import CareerProfile
from ..paths import PROFILE_DIR


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


def merge_section(
    section: str, data: str, name: str = "default"
) -> CareerProfile:
    """将 data 合并到档案的指定 section 并保存。

    data 尝试按 JSON 解析；如果不是合法 JSON，则存为 {"raw": data}。

    Args:
        section: 目标 section（who/have/want/gap/plan）。
        data: LLM 传来的字符串，期望是 JSON。
        name: 档案名称，默认 "default"。

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
    source: str, import_file: str | None = None, name: str = "default"
) -> CareerProfile:
    """保存当前 plan 到版本历史。

    Args:
        source: 来源标识（"generated" | "imported" | "manual"）
        import_file: 如果是导入的，记录文件路径
        name: 档案名称，默认 "default"

    Returns:
        更新后的档案。
    """
    profile = load_profile(name)
    profile.save_plan_snapshot(source, import_file)
    save_profile(profile, name)
    return profile
