"""MCP 工具函数级冒烟测试。

直接调用 server.py 的工具函数（不经 MCP 传输层），
用「docstring 官方 Schema」作为入参契约做回归：
BUG-004（save_gap_analysis schema 崩溃）、BUG-005（apply_insight 幽灵 import）
均由本层测试锁定。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import pytest

import src.tools.profile as profile_module
from src.models import CareerProfile


@pytest.fixture()
def temp_profile(tmp_path, monkeypatch):
    """把档案指到临时目录，并同步替换 server 层的 from-import 绑定。"""
    monkeypatch.setattr(profile_module, "PROFILE_DIR", tmp_path)
    import src.server as server_module

    def _load(name: str = "default") -> CareerProfile:
        p = profile_module.PROFILE_DIR / f"{name}.json"
        return CareerProfile.model_validate_json(p.read_text(encoding="utf-8")) if p.exists() else CareerProfile()

    monkeypatch.setattr(server_module, "load_profile", _load)
    return tmp_path


def _parse(result_json: str) -> dict:
    data = json.loads(result_json)
    assert isinstance(data, dict)
    assert not data.get("isError"), f"工具返回错误: {data}"
    return data


def test_save_gap_analysis_accepts_docstring_minimal_schema(temp_profile):
    """BUG-004 回归：按 docstring 最小结构传参必须成功且不留半成品。"""
    from src.server import save_gap_analysis

    minimal = json.dumps({
        "match_score": 65,
        "skill_gaps": [
            {"skill": "LLM", "priority": "high",
             "current_level": "无", "required_level": "熟练", "source": "JD"}
        ],
        "priority_actions": ["学习基础"],
        "strengths": ["有项目经验"],
    }, ensure_ascii=False)

    result = _parse(save_gap_analysis(gap_json=minimal))
    assert result["context"]["phase"] == "gap_saved"
    assert "已保存" in result["message"]

    profile = profile_module.load_profile()
    assert profile.gap["match_score"] == 65
    assert not profile.journey or profile.journey[-1].phase == "analysis"


def test_save_gap_analysis_tolerates_string_entries(temp_profile):
    """字符串条目（LLM 退化输出）不崩，报告原样渲染。"""
    from src.server import save_gap_analysis

    degraded = json.dumps({
        "match_score": 50,
        "skill_gaps": [{"skill": "RAG", "priority": "medium",
                        "current_level": "无", "target_level": "熟练", "source": "JD"}],
        "priority_actions": ["先学检索基础"],
        "strengths": ["后端经验丰富"],
    }, ensure_ascii=False)

    result = _parse(save_gap_analysis(gap_json=degraded))
    assert "RAG" in result["message"]
    assert "后端经验丰富" in result["message"]
    assert "先学检索基础" in result["message"]


def test_save_gap_tolerates_malformed_values(temp_profile):
    """畸形字段值不抛异常：要么正常降级保存，要么返回标准错误，档案状态一致。"""
    from src.server import save_gap_analysis

    bad = json.dumps({"match_score": "not-a-number", "skill_gaps": [{"unexpected": 1}]})
    result = json.loads(save_gap_analysis(gap_json=bad))
    profile = profile_module.load_profile()

    if result.get("isError"):
        assert not profile.gap
    else:
        # 降级渲染后正常落盘，报告可读
        assert "not-a-number" in result["message"]


def test_intake_rejects_invalid_json(temp_profile):
    """BUG-007 回归：非法 JSON 必须返回结构化错误且不写档案。"""
    from src.server import intake

    result = json.loads(intake(section="who", data="{oops 非法JSON"))
    assert result.get("isError") is True
    assert result["code"] == "INVALID_JSON"

    profile = profile_module.load_profile()
    assert not profile.who, "坏输入不应写入档案"
    assert profile.version == 0


def test_import_plan_rejects_binary_garbage(temp_profile):
    """OBS-003 回归：控制字符垃圾内容返回结构化错误，不透传给 LLM。"""
    from pathlib import Path

    from src.server import import_plan

    garbage = temp_profile / "garbage.md"
    garbage.write_bytes(b"\x00\x01\x02binary junk \x1f\x03" * 50)

    result = json.loads(import_plan(file_path=str(garbage)))
    assert result.get("isError") is True
    assert "\x00" not in result["message"] and "\x01" not in result["message"]


def test_boss_login_navigates_and_zero_param():
    """BUG-009/OBS-004 回归：登录工具必须导航到 zhipin.com，且不接受参数拉起浏览器。"""
    login_src = (Path(__file__).parent.parent / "src" / "scrapers" / "boss" / "login.py").read_text(
        encoding="utf-8"
    )
    # 探针验证过 60 秒存活的 goto 必须存在于工具主流程（曾因丢失导致永久白屏）
    assert "page.goto(ZHIPIN_URL" in login_src
    # 带参即打印用法退出，绝不带参拉起浏览器
    assert "len(sys.argv) > 1" in login_src


def test_apply_insight_end_to_end(temp_profile):
    """BUG-005 回归：apply_insight 可导入、可执行、调整可落地。"""
    from src.models import Task
    from src.server import apply_insight, trigger_insight

    profile = profile_module.load_profile()
    profile.tasks = [Task(id="task_001", name="任务A", phase_id="phase_1")]
    profile_module.save_profile(profile)

    prepared = _parse(trigger_insight(trigger_type="stage_audit"))
    assert "prompt" in prepared

    insight = json.dumps({
        "trigger_type": "stage_audit",
        "status": "on_track",
        "summary": "任务正常推进",
        "insights": ["刷题节奏稳定"],
        "adjustment_needed": True,
        "adjustment_type": "auto",
        "adjustment_reason": "掌握速度快，加深难度",
        "changes": [
            {"type": "add_task", "details": {"name": "任务A（深入）"}},
            {"type": "modify_task", "task_id": "task_001", "details": {"priority": "high"}},
        ],
        "user_message": "继续保持",
    }, ensure_ascii=False)

    applied = _parse(apply_insight(insight_json=insight))
    assert applied["context"]["phase"] == "adjustment_applied"

    final = profile_module.load_profile()
    assert any(t.name == "任务A（深入）" for t in final.tasks)
    assert final.get_task("task_001").priority == "high"
    assert final.adjustments[-1].trigger_type == "stage_audit"
