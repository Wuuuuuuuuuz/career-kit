"""档案管理测试——多档案切换、回收站式删除、恢复、active 回退、名称安全。"""

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
    monkeypatch.setattr(server_module, "profile_exists", profile_module.profile_exists)
    monkeypatch.setattr(server_module, "do_list_profiles", profile_module.list_profiles)
    monkeypatch.setattr(server_module, "do_list_trash", profile_module.list_trash)
    monkeypatch.setattr(server_module, "get_active_profile_name", profile_module.get_active_profile_name)
    monkeypatch.setattr(server_module, "set_active_profile_name", profile_module.set_active_profile_name)
    monkeypatch.setattr(server_module, "do_delete_profile", profile_module.delete_profile)
    monkeypatch.setattr(server_module, "do_restore_profile", profile_module.restore_profile)
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


# === 回收站式删除 ===


def test_delete_profile_moves_to_trash(temp_profile):
    """删除 = 移入回收站，原文件消失、回收站出现。"""
    _build("alice", "Alice", "AI 工程师")

    target = profile_module.delete_profile("alice")

    assert target is not None
    assert not (profile_module.PROFILE_DIR / "alice.json").exists()
    assert target.exists() and target.parent.name == "trash"

    # 回收站内容可列出，档案名可还原
    items = profile_module.list_trash()
    assert len(items) == 1
    assert items[0]["profile_name"] == "alice"


def test_delete_profile_repeated_keeps_history(temp_profile):
    """同名档案多次删除：回收站保留多份，不互相覆盖。"""
    _build("alice", "Alice")
    first = profile_module.delete_profile("alice")
    _build("alice", "Alice")
    second = profile_module.delete_profile("alice")

    assert first is not None and second is not None
    assert first != second
    assert len(profile_module.list_trash()) == 2


def test_delete_profile_missing_returns_none(temp_profile):
    """删除不存在的档案返回 None。"""
    assert profile_module.delete_profile("nobody") is None


def test_delete_active_falls_back_to_default(temp_profile):
    """允许删除当前活跃档案；删除后 active 自动回退 default，不悬挂。"""
    _build("alice", "Alice")
    profile_module.set_active_profile_name("alice")
    assert profile_module.get_active_profile_name() == "alice"

    assert profile_module.delete_profile("alice") is not None
    assert profile_module.get_active_profile_name() == "default"

    # 无参读写落到 default，不报错
    profile_module.merge_section("who", '{"name": "默认用户"}')
    assert profile_module.load_profile("default").who["name"] == "默认用户"


def test_restore_profile(temp_profile):
    """restore 从回收站恢复档案，数据完整。"""
    _build("alice", "Alice", "AI 工程师")
    profile_module.delete_profile("alice")

    restored = profile_module.restore_profile("alice")
    assert restored is not None
    assert (profile_module.PROFILE_DIR / "alice.json").exists()

    p = profile_module.load_profile("alice")
    assert p.who["name"] == "Alice"
    assert p.want["target_role"] == "AI 工程师"
    # 回收站已清空该档案
    assert not profile_module.list_trash()


def test_restore_profile_conflict_rejected(temp_profile):
    """目标位置已有同名档案时拒绝恢复（防覆盖新数据）。"""
    _build("alice", "Alice")
    profile_module.delete_profile("alice")
    _build("alice", "AliceV2")  # 删除后又新建

    with pytest.raises(ValueError):
        profile_module.restore_profile("alice")
    # 新数据未被覆盖
    assert profile_module.load_profile("alice").who["name"] == "AliceV2"


def test_restore_profile_missing_returns_none(temp_profile):
    """回收站无此档案时返回 None。"""
    assert profile_module.restore_profile("nobody") is None


def test_invalid_profile_name_rejected(temp_profile):
    """非法档案名（路径穿越/非法字符）被拒绝。"""
    _build("alice", "Alice")

    for bad in ("../evil", "a/b", "a\\b", "..", "", "a b", "a:b"):
        with pytest.raises(ValueError):
            profile_module.load_profile(bad)
        with pytest.raises(ValueError):
            profile_module.save_profile(CareerProfile(), bad)
        with pytest.raises(ValueError):
            profile_module.set_active_profile_name(bad)
        with pytest.raises(ValueError):
            profile_module.delete_profile(bad)
        with pytest.raises(ValueError):
            profile_module.restore_profile(bad)

    # 合法名不受影响
    assert profile_module.load_profile("alice").who["name"] == "Alice"


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

    # 非法档案名 → 结构化错误
    result = json.loads(switch_profile(profile_name="../evil"))
    assert result.get("isError") is True
    assert result["code"] == "INVALID_SECTION"


def test_mcp_delete_profile_requires_confirm(temp_profile):
    """confirm 缺省时拒绝删除，仅提示确认。"""
    _build("alice", "Alice")

    from src.server import delete_profile

    out = delete_profile(profile_name="alice")
    assert "确认" in out
    assert (profile_module.PROFILE_DIR / "alice.json").exists()
    assert not profile_module.list_trash()

    # confirm 非 "true" 同样拒绝
    out2 = delete_profile(profile_name="alice", confirm="yes")
    assert (profile_module.PROFILE_DIR / "alice.json").exists()


def test_mcp_delete_profile_confirmed_moves_to_trash(temp_profile):
    """confirm="true" 执行回收站式删除；删除 active 后系统回退 default。"""
    _build("alice", "Alice")
    _build("bob", "Bob")
    profile_module.set_active_profile_name("alice")

    from src.server import delete_profile

    out = delete_profile(profile_name="bob", confirm="true")
    assert "已删除档案「bob」" in out
    assert "回收站" in out and "restore_profile" in out
    assert not (profile_module.PROFILE_DIR / "bob.json").exists()
    assert len(profile_module.list_trash()) == 1

    # 删除当前活跃档案也允许（回收站可恢复），并回退 default
    out2 = delete_profile(profile_name="alice", confirm="true")
    assert "已删除档案「alice」" in out2
    assert profile_module.get_active_profile_name() == "default"

    # 删除不存在的档案 → 错误
    result = json.loads(delete_profile(profile_name="nobody", confirm="true"))
    assert result.get("isError") is True
    assert result["code"] == "MISSING_DATA"


def test_mcp_restore_profile(temp_profile):
    """restore_profile 工具恢复档案并返回摘要。"""
    _build("alice", "Alice", "AI 工程师")
    profile_module.delete_profile("alice")

    from src.server import restore_profile

    out = restore_profile(profile_name="alice")
    assert "已恢复档案「alice」" in out
    assert "Alice" in out and "AI 工程师" in out

    # 回收站没有的档案 → 错误
    result = json.loads(restore_profile(profile_name="nobody"))
    assert result.get("isError") is True
    assert result["code"] == "MISSING_DATA"

    # 目标已存在同名 → 拒绝
    profile_module.delete_profile("alice")
    _build("alice", "AliceV2")
    result = json.loads(restore_profile(profile_name="alice"))
    assert result.get("isError") is True
    assert "已存在" in result["message"]


def test_mcp_list_trash(temp_profile):
    """list_trash 工具展示回收站内容。"""
    from src.server import list_trash

    assert "回收站为空" in list_trash()

    _build("alice", "Alice")
    profile_module.delete_profile("alice")
    out = list_trash()
    assert "alice" in out
    assert "restore_profile" in out


def test_mcp_workflow_status_marks_active(temp_profile):
    """get_workflow_status 标注当前档案名，切换后 LLM 有感知。"""
    _build("alice", "Alice")
    profile_module.set_active_profile_name("alice")

    from src.server import get_workflow_status

    out = get_workflow_status()
    assert "alice" in out

    profile_module.set_active_profile_name("default")
    out2 = get_workflow_status()
    assert "default" in out2


def test_mcp_start_session_marks_active(temp_profile):
    """start_session 标注当前档案名。"""
    _build("alice", "Alice")
    profile_module.set_active_profile_name("alice")

    from src.server import start_session

    out = start_session()
    assert "当前档案：alice" in out
