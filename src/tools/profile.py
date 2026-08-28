"""档案管理——初始化会话、逐步填充、确认档案、多档案切换。

多档案机制：
- 档案文件为 PROFILE_DIR/{name}.json，名称任意（默认 "default"）。
- 当前活跃档案记录在 PROFILE_DIR/.active_profile，无记录时回退 "default"。
- 不传 name 的所有读写操作都作用于当前活跃档案；
  显式传 name 的操作不受影响（测试/切换场景用）。

删除采用回收站式：delete_profile 把档案移入 PROFILE_DIR/trash/ 而非直接删除，
restore_profile 可从回收站恢复——用户数据是长期资产，删除必须可逆。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models import CareerProfile
from ..paths import PROFILE_DIR

ACTIVE_PROFILE_FILE = ".active_profile"

# 档案名白名单：防止路径穿越（"../x"、子目录、非法字符一律拒绝）
PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_profile_name(name: str) -> str:
    """校验档案名，非法时抛 ValueError。"""
    if not name or not PROFILE_NAME_RE.match(name):
        raise ValueError(
            f"非法档案名「{name}」：只允许字母、数字、下划线、连字符"
        )
    return name


def get_active_profile_name() -> str:
    """读取当前活跃档案名，未设置或档案已不存在时回退 "default"。"""
    try:
        name = (PROFILE_DIR / ACTIVE_PROFILE_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        name = ""
    if not name:
        return "default"
    # 悬挂检测：active 指向的档案被删除后回退 default，避免读写落到空档案
    if not (PROFILE_DIR / f"{name}.json").exists():
        return "default"
    return name


def set_active_profile_name(name: str) -> None:
    """把指定档案设为当前活跃档案。"""
    validate_profile_name(name)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    (PROFILE_DIR / ACTIVE_PROFILE_FILE).write_text(name, encoding="utf-8")


def profile_exists(name: str) -> bool:
    """档案文件是否存在。非法档案名抛 ValueError。"""
    validate_profile_name(name)
    return (PROFILE_DIR / f"{name}.json").exists()


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


# === 回收站式删除 ===


def _trash_dir() -> Path:
    return PROFILE_DIR / "trash"


def delete_profile(name: str) -> Path | None:
    """把档案移入回收站（可恢复）。返回回收站文件路径，档案不存在返回 None。

    非法档案名抛 ValueError。注意：回收站式删除是安全操作，允许删除当前
    活跃档案——get_active_profile_name 会自动回退到 default。
    """
    validate_profile_name(name)
    path = PROFILE_DIR / f"{name}.json"
    if not path.exists():
        return None

    trash_dir = _trash_dir()
    trash_dir.mkdir(parents=True, exist_ok=True)

    # 同名档案多次删除：加时间戳区分，保留所有历史
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = trash_dir / f"{name}.json"
    if target.exists():
        target = trash_dir / f"{name}_{ts}.json"

    path.rename(target)
    return target


def list_trash() -> list[dict[str, Any]]:
    """列出回收站里的档案（可恢复项）。"""
    trash_dir = _trash_dir()
    if not trash_dir.exists():
        return []
    items = []
    for path in sorted(trash_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        items.append({
            "file": path.name,
            "profile_name": _trash_base_name(path.name),
            "deleted_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        })
    return items


def _trash_base_name(filename: str) -> str:
    """从回收站文件名还原档案名：alice.json → alice；alice_20260828_120000.json → alice。"""
    return filename.split("_", 1)[0] if "_" in filename else Path(filename).stem


def restore_profile(name: str) -> Path | None:
    """从回收站恢复最新一份档案。回收站无此档案返回 None。

    目标位置已存在同名档案时抛 ValueError（拒绝覆盖新数据，防误恢复）。
    """
    validate_profile_name(name)
    target = PROFILE_DIR / f"{name}.json"
    if target.exists():
        raise ValueError(f"档案「{name}」已存在，拒绝覆盖——如需恢复请先处理现有档案")

    trash_dir = _trash_dir()
    if not trash_dir.exists():
        return None

    candidates = [p for p in trash_dir.glob(f"{name}*.json")]
    if not candidates:
        return None
    # 取最新一份（mtime 最大）
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    latest.rename(target)
    return target


def load_profile(name: str | None = None) -> CareerProfile:
    """从本地加载档案，不存在则返回空档案。

    name 为 None 时加载当前活跃档案（未设置则回退 "default"）。
    """
    if name is None:
        name = get_active_profile_name()
    else:
        validate_profile_name(name)
    path = PROFILE_DIR / f"{name}.json"
    if path.exists():
        return CareerProfile.model_validate_json(path.read_text(encoding="utf-8"))
    return CareerProfile()


def save_profile(profile: CareerProfile, name: str | None = None) -> None:
    """保存档案到本地。name 为 None 时保存到当前活跃档案。"""
    if name is None:
        name = get_active_profile_name()
    else:
        validate_profile_name(name)
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
