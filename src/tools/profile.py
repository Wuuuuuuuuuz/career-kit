"""档案管理——初始化会话、逐步填充、确认档案。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..models import CareerProfile

# 优先级：环境变量 > 当前工作目录/.career-kit
PROFILE_DIR = Path(os.environ.get("CAREER_KIT_DATA_DIR", Path.cwd() / ".career-kit"))


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


def get_plan_history(name: str = "default") -> list[dict[str, Any]]:
    """获取计划版本历史列表。

    Args:
        name: 档案名称，默认 "default"

    Returns:
        版本历史列表，每个元素包含 version、timestamp、source、import_file
    """
    profile = load_profile(name)
    return [
        {
            "version": v.version,
            "timestamp": v.timestamp,
            "source": v.source,
            "import_file": v.import_file,
            "summary": _summarize_plan(v.content),
        }
        for v in profile.plan_history
    ]


def restore_plan_version(version: int, name: str = "default") -> CareerProfile:
    """恢复到指定版本的计划。

    Args:
        version: 要恢复的版本号
        name: 档案名称，默认 "default"

    Returns:
        更新后的档案。

    Raises:
        ValueError: 如果版本号不存在
    """
    profile = load_profile(name)
    profile.restore_plan_version(version)
    save_profile(profile, name)
    return profile


def _summarize_plan(plan: dict[str, Any], max_len: int = 100) -> str:
    """生成计划的简短摘要。"""
    if not plan:
        return "（空计划）"
    text = str(plan)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text
