"""档案管理测试——多档案切换、列表、删除、active 回退。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import pytest

import src.tools.profile as profile_module
from src.models import CareerProfile

# server.py 的 from-import 绑定需同步替换
import src.server as server_module


@pytest.fixture()
def temp_profile(tmp_path, monkeypatch):
    """把档案指到临时目录，并同步替换 server 层的 from-import 绑定。"""
    monkeypatch.setattr(profile_module, "PROFILE_DIR", tmp_path)

    def _load(name: str | None = None) -> CareerProfile:
        n = name or profile_module.get_active_profile_name()
        p = profile_module.PROFILE_DIR / f"{n}.json"
        return CareerProfile.model_validate_json(p.read_text(encoding="utf-8")) if p.exists() else CareerProfile()

    monkeypatch.setattr(server_module, "load_profile", _load)
    monkeypatch.setattr(server_module, "do_list_profiles", profile_module.list_profiles)
    monkeypatch.setattr(server_module, "get_active_profile_name", profile_module.get_active_profile_name)
    monkeypatch.setattr(server_module, "set_active_profile_name", profile_module.set_active_profile_name)
    monkeypatch.setattr(server_module, "do_delete_profile", profile_module.delete_profile)
    return tmp_path


def _build(name: str, who: str, want: str = "") -> None:
    """在指定档案下写入 who/want。"""
    profile_module.merge_section("who", json.dumps({"name": who}, ensure_ascii=False), name)
    if want:
        profile_module.merge_section("want", json.dumps({"target_role": want}, ensure_ascii=False), name)


def test_default_fallback_without_active_file(temp_profile):
    """无 .active_profile 时回退 default，行为与旧版一致。"""
    assert profile_module.get_active_profile_name() == "default"

    p = profile_module.load_profile()
    assert isinstance(p, CareerProfile) and not p.who

    profile_module.merge_section("who", '{"name": "默认用户"}')
    assert (profile_module.PROFILE_DIR / "default.json").exists()
    assert not (profile_module.PROFILE_DIR / profile_module.ACTIVE_PROFILE_FILE).exists()


def test_switch_profile_isolates_data(temp_profile):
    """切换档案后，无参读写操作落到新档案，数据互不污染。"""
    _build("alice", "Alice", "AI 工程师")
    _build("bob", "Bob", "前端工程师")

    # 默认在 default
    assert profile_module.get_active_profile_name() == "default"

    # 切到 alice：无参读写生效
    profile_module.set_active_profile_name("alice")
    assert profile_module.get_active_profile_name() == "alice"
    p = profile_module.load_profile()
    assert p.who["name"] == "Alice"
    assert p.want["target_role"] == "AI 工程师"

    # 在 alice 上写数据，不影响 bob
    profile_module.merge_section("have", '{"skills": ["Python"]}')
    p2 = profile_module.load_profile("bob")
    assert "skills" not in p2.have
    assert profile_module.load_profile("alice").have["skills"] == ["Python"]

    # 切回 bob
    profile_module.set_active_profile_name("bob")
    assert profile_module.load_profile().who["name"] == "Bob"


def test_switch_profile_save_targets_active(temp_profile):
    """save_profile 无参保存到当前活跃档案。"""
    _build("alice", "Alice")
    profile_module.set_active_profile_name("alice")

    p = profile_module.load_profile()
    p.want = {"target_role": "后端工程师"}
    profile_module.save_profile(p)

    assert profile_module.load_profile("alice").want["target_role"] == "后端工程师"
    assert "后端工程师" not in profile_module.load_profile("default").want


def test_list_profiles_shows_meta_and_active(temp_profile):
    """list_profiles 返回档案元信息，并标记当前活跃档案。"""
    _build("alice", "Alice", "AI 工程师")
    _build("bob", "Bob")
    profile_module.set_active_profile_name("bob")

    profiles = profile_module.list_profiles()
    names = [p["name"] for p in profiles]

    assert "alice" in names and "bob" in names
    alice = next(p for p in profiles if p["name"] == "alice")
    bob = next(p for p in profiles if p["name"] == "bob")

    assert alice["is_active"] is False
    assert alice["person"] == "Alice"
    assert alice["target"] == "AI 工程师"
    assert bob["is_active"] is True
    assert bob["has_plan"] is False


def test_delete_profile_rejects_active(temp_profile):
    """当前活跃档案禁止删除。"""
    _build("alice", "Alice")
    profile_module.set_active_profile_name("alice")

    assert profile_module.delete_profile("alice") is False
    assert (profile_module.PROFILE_DIR / "alice.json").exists()
    assert profile_module.get_active_profile_name() == "alice"


def test_delete_profile_removes_other(temp_profile):
    """非活跃档案可删除；删除后 load 为空档案。"""
    _build("alice", "Alice")
    _build("bob", "Bob")
    profile_module.set_active_profile_name("alice")

    assert profile_module.delete_profile("bob") is True
    assert not (profile_module.PROFILE_DIR / "bob.json").exists()
    remaining = [p["name"] for p in profile_module.list_profiles()]
    assert "bob" not in remaining and "alice" in remaining

    # 删除不存在的档案返回 False
    assert profile_module.delete_profile("nobody") is False


# === MCP 工具层 ===


def test_mcp_list_profiles(temp_profile):
    """list_profiles 工具返回可读列表与当前标记。"""
    _build("alice", "Alice", "AI 工程师")
    profile_module.set_active_profile_name("alice")

    from src.server import list_profiles

    out = list_profiles()
    assert "alice" in out
    assert "Alice" in out
    assert "AI 工程师" in out
    assert "当前使用" in out


def test_mcp_switch_profile(temp_profile):
    """switch_profile 工具切换并返回新档案摘要。"""
    _build("alice", "Alice", "AI 工程师")

    from src.server import switch_profile

    out = switch_profile(profile_name="alice")
    assert "已切换到档案「alice」" in out
    assert "AI 工程师" in out
    assert profile_module.get_active_profile_name() == "alice"

    # 不存在的档案 → 结构化错误
    result = json.loads(switch_profile(profile_name="nobody"))
    assert result.get("isError") is True
    assert result["code"] == "MISSING_DATA"
    assert profile_module.get_active_profile_name() == "alice"


def test_mcp_delete_profile(temp_profile):
    """delete_profile 工具：拒绝删除当前档案，可删其他。"""
    _build("alice", "Alice")
    _build("bob", "Bob")
    profile_module.set_active_profile_name("alice")

    from src.server import delete_profile

    # 删除当前档案被拒绝
    result = json.loads(delete_profile(profile_name="alice"))
    assert result.get("isError") is True
    assert result["code"] == "INVALID_SECTION"
    assert "禁止删除" in result["message"]
    assert (profile_module.PROFILE_DIR / "alice.json").exists()

    # 删除其他档案成功
    out = delete_profile(profile_name="bob")
    assert "已删除档案「bob」" in out
    assert "剩余档案" in out

    # 删除不存在的档案 → 错误
    result = json.loads(delete_profile(profile_name="nobody"))
    assert result.get("isError") is True
    assert result["code"] == "MISSING_DATA"
