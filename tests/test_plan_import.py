"""计划导入功能测试。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8')

from src.models import CareerProfile, PlanVersion
from src.tools.plan_importer import compare_plans, format_diff_report, parse_plan_file
from src.tools.profile import (
    get_plan_history,
    load_profile,
    merge_section,
    restore_plan_version,
    save_plan_snapshot,
    save_profile,
)

TEST_PLAN_FILE = Path(__file__).parent.parent / "dev" / "test" / "计划1.md"


def test_plan_parser():
    """测试计划文件解析。"""
    print("=" * 60)
    print("测试 1: 计划文件解析")
    print("=" * 60)

    if not TEST_PLAN_FILE.exists():
        print("[SKIP] 测试文件不存在")
        return

    text = parse_plan_file(str(TEST_PLAN_FILE))
    print(f"[OK] 解析成功，共 {len(text)} 字符")

    # 验证关键内容
    assert "筑基攻坚期" in text
    assert "TokenSaver" in text
    assert "2027" in text
    print("[OK] 关键内容验证通过")

    print(f"\n前 300 字符预览:\n{'-' * 40}")
    print(text[:300])
    print(f"{'-' * 40}\n")


def test_version_management():
    """测试版本管理功能。"""
    print("=" * 60)
    print("测试 2: 版本管理")
    print("=" * 60)

    # 使用临时目录
    import src.tools.profile as profile_module
    original_dir = profile_module.PROFILE_DIR

    with tempfile.TemporaryDirectory() as tmpdir:
        profile_module.PROFILE_DIR = Path(tmpdir)

        # 创建初始档案
        profile = CareerProfile()
        profile.plan = {"phases": ["阶段1", "阶段2"], "timeline": "6个月"}
        save_profile(profile, "test")

        # 保存版本快照
        save_plan_snapshot("generated", name="test")
        print("[OK] 保存第一个版本快照")

        # 修改计划
        profile = load_profile("test")
        profile.plan = {"phases": ["新阶段1", "新阶段2", "新阶段3"], "timeline": "12个月"}
        save_profile(profile, "test")

        # 保存第二个版本快照
        save_plan_snapshot("imported", "/path/to/plan.md", name="test")
        print("[OK] 保存第二个版本快照")

        # 查看版本历史
        history = get_plan_history("test")
        assert len(history) == 2
        assert history[0]["source"] == "generated"
        assert history[1]["source"] == "imported"
        print(f"[OK] 版本历史共 {len(history)} 个版本")

        # 恢复到第一个版本
        profile = restore_plan_version(1, "test")
        assert len(profile.plan["phases"]) == 2
        print("[OK] 恢复到版本 1 成功")

        # 验证恢复后的历史（应该有3个：原始2个 + 恢复前保存的）
        history = get_plan_history("test")
        print(f"[OK] 恢复后版本历史共 {len(history)} 个版本")

        profile_module.PROFILE_DIR = original_dir

    print()


def test_compare_plans():
    """测试计划对比功能。"""
    print("=" * 60)
    print("测试 3: 计划对比")
    print("=" * 60)

    old_plan = {
        "phases": ["阶段1", "阶段2"],
        "timeline": "6个月",
        "focus": "前端",
    }

    new_plan = {
        "phases": ["新阶段1", "新阶段2", "新阶段3"],
        "timeline": "12个月",
        "priority": "高",
    }

    diff = compare_plans(old_plan, new_plan)

    # 验证差异
    assert len(diff["added"]) == 1  # priority
    assert len(diff["removed"]) == 1  # focus
    assert len(diff["modified"]) == 2  # phases, timeline
    assert len(diff["unchanged"]) == 0
    print("[OK] 差异分析正确")

    # 格式化报告
    report = format_diff_report(diff)
    assert "新增内容" in report
    assert "删除内容" in report
    assert "修改内容" in report
    print("[OK] 报告格式化成功")

    print(f"\n差异报告预览:\n{'-' * 40}")
    print(report)
    print(f"{'-' * 40}\n")


def test_full_import_flow():
    """测试完整的计划导入流程。"""
    print("=" * 60)
    print("测试 4: 完整导入流程")
    print("=" * 60)

    import src.tools.profile as profile_module
    original_dir = profile_module.PROFILE_DIR

    with tempfile.TemporaryDirectory() as tmpdir:
        profile_module.PROFILE_DIR = Path(tmpdir)

        # 模拟首次导入（无旧计划）
        profile = CareerProfile()
        save_profile(profile, "test")

        # 解析计划文件
        if TEST_PLAN_FILE.exists():
            plan_text = parse_plan_file(str(TEST_PLAN_FILE))
            print(f"[OK] 解析计划文件，{len(plan_text)} 字符")

            # 模拟 LLM 解析后的结构化数据
            plan_data = {
                "phases": [
                    {"name": "筑基攻坚期", "duration": "8周", "period": "2026.08-2026.09"},
                    {"name": "深耕背书期", "duration": "16周", "period": "2026.10-2027.01"},
                    {"name": "暑期实习冲刺期", "duration": "16周", "period": "2027.02-2027.05"},
                    {"name": "转正+秋招兜底期", "duration": "16周", "period": "2027.06-2027.09"},
                ],
                "total_duration": "56周",
                "key_milestones": [
                    "2027年2月大厂暑期实习提前批",
                    "2027年6月秋招提前批",
                ],
            }

            # 填充 plan
            profile = merge_section("plan", json.dumps(plan_data), "test")
            print(f"[OK] 填充 plan section，版本 v{profile.version}")

            # 保存版本快照
            save_plan_snapshot("imported", str(TEST_PLAN_FILE), "test")
            print("[OK] 保存导入版本快照")

            # 验证版本历史
            history = get_plan_history("test")
            assert len(history) == 1
            assert history[0]["source"] == "imported"
            print("[OK] 版本历史验证通过")

        profile_module.PROFILE_DIR = original_dir

    print()


def test_mcp_tools():
    """测试 MCP tools 注册。"""
    print("=" * 60)
    print("测试 5: MCP Tools 注册")
    print("=" * 60)

    from src.server import mcp

    tools = [t.name for t in mcp._tool_manager.list_tools()]

    new_tools = ["import_plan", "compare_plan_versions", "replace_plan",
                 "merge_plan", "list_plan_versions", "restore_plan"]

    for tool in new_tools:
        assert tool in tools, f"工具 {tool} 未注册"
        print(f"[OK] {tool} 已注册")

    print()


def main():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("计划导入功能测试套件")
    print("=" * 60 + "\n")

    tests = [
        test_plan_parser,
        test_version_management,
        test_compare_plans,
        test_full_import_flow,
        test_mcp_tools,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            print()

    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
