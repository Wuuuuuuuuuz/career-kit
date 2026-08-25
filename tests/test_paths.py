"""数据根目录解析——单一来源 src/paths.py 的行为锁定。"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import src.paths as paths


def _reload_with_env(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv("CAREER_KIT_DATA_DIR", raising=False)
    else:
        monkeypatch.setenv("CAREER_KIT_DATA_DIR", value)
    importlib.reload(paths)


def test_default_root_is_home_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    _reload_with_env(monkeypatch, None)
    assert paths.DATA_ROOT == Path.home() / ".career-kit"
    assert paths.PROFILE_DIR == paths.DATA_ROOT
    assert paths.KNOWLEDGE_DIR == paths.DATA_ROOT / "knowledge"
    assert paths.CACHE_DIR == paths.DATA_ROOT / "cache"


def test_env_var_overrides_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _reload_with_env(monkeypatch, str(tmp_path))
    assert paths.DATA_ROOT == tmp_path
    assert paths.KNOWLEDGE_DIR == tmp_path / "knowledge"
    assert paths.CACHE_DIR == tmp_path / "cache"


def test_modules_share_paths_constants(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """业务模块的目录常量必须来自 paths.py，禁止各自拼路径。"""
    from src.scrapers import knowledge_writer
    from src.tools import knowledge_search, profile

    _reload_with_env(monkeypatch, str(tmp_path))
    importlib.reload(knowledge_writer)
    importlib.reload(knowledge_search)
    importlib.reload(profile)

    try:
        assert knowledge_writer.KNOWLEDGE_DIR == tmp_path / "knowledge"
        assert knowledge_search.KNOWLEDGE_DIR == tmp_path / "knowledge"
        assert profile.PROFILE_DIR == tmp_path
    finally:
        # 还原其他模块的常量绑定，避免污染后续测试
        _reload_with_env(monkeypatch, None)
        importlib.reload(knowledge_writer)
        importlib.reload(knowledge_search)
        importlib.reload(profile)
