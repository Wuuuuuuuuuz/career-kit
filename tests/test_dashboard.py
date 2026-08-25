"""export_dashboard 冒烟测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_export_dashboard_smoke(tmp_path, monkeypatch):
    """生成自包含 HTML，内嵌阶段进度与能力证据。"""
    import src.tools.profile as profile_module
    from src.server import checkin_task, export_dashboard, generate_tasks, intake
    from src.tools.roadmap import parse_roadmap
    from src.models import CareerProfile
    import json as jsonlib

    monkeypatch.setattr(profile_module, "PROFILE_DIR", tmp_path)
    # server.py 的 load_profile 是 from-import 绑定，需要同步替换
    import src.server as server_module
    monkeypatch.setattr(server_module, "load_profile", lambda name="default": CareerProfile.model_validate_json((profile_module.PROFILE_DIR / f"{name}.json").read_text(encoding="utf-8")) if (profile_module.PROFILE_DIR / f"{name}.json").exists() else CareerProfile())

    intake("who", '{"name":"冒烟"}')
    profile = profile_module.load_profile()
    profile.plan = parse_roadmap(jsonlib.dumps({
        "roadmap": {"phases": [{"type": "learn", "name": "基础", "goal": "入门",
                                "milestones": [{"name": "M1", "tasks": [{"name": "任务A"}, {"name": "任务B"}]}]}]}
    }, ensure_ascii=False))
    profile.touch()
    profile_module.save_profile(profile)

    generate_tasks()
    result = checkin_task(task_id="task_001", status="completed", notes="冒烟打卡")
    assert "已打卡" in result or "已跳过" not in result

    out = export_dashboard()
    assert "career_kit_dashboard.html" in out

    html = Path(Path(out.split("：")[1].split("\n")[0].strip())).read_text(encoding="utf-8")
    assert "基础" in html          # 阶段名
    assert "冒烟打卡" in html      # 能力证据 notes 已内嵌
    assert "task-deadline" not in html and "超期" not in html  # 无时间概念残留
