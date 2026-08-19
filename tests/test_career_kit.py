"""Career Kit 集成测试——直接运行看结果。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import CareerProfile
from src.tools.profile import load_profile, merge_section, save_profile
from src.tools.resume_parser import extract_text
from src.tools.session import get_welcome_message


def test_models_merge():
    """测试 CareerProfile 的 merge 功能。"""
    print("=" * 50)
    print("测试 1: CareerProfile merge")
    print("=" * 50)

    p = CareerProfile()

    # 测试基本合并
    p.merge("who", {"name": "张三", "education": "本科"})
    assert p.who == {"name": "张三", "education": "本科"}
    assert p.version == 1
    print("[PASS] 基本合并成功")

    # 测试追加字段
    p.merge("who", {"age": 25})
    assert p.who == {"name": "张三", "education": "本科", "age": 25}
    assert p.version == 2
    print("[PASS] 追加字段成功")

    # 测试嵌套合并
    p.merge("have", {"skills": ["Python", "React"]})
    p.merge("have", {"skills": ["Go"], "experience": "3年"})
    # 注意：skills 是列表，不是字典，所以会被替换而不是合并
    assert p.have == {"skills": ["Go"], "experience": "3年"}
    assert p.version == 4
    print("[PASS] 列表字段替换成功")

    # 测试嵌套字典合并
    p.merge("want", {"target": {"role": "前端", "salary": "20k"}})
    p.merge("want", {"target": {"city": "北京"}})
    assert p.want == {"target": {"role": "前端", "salary": "20k", "city": "北京"}}
    print("[PASS] 嵌套字典合并成功")

    # 测试无效 section
    try:
        p.merge("invalid", {"test": 1})
        assert False, "应该抛出异常"
    except ValueError as e:
        print(f"[PASS] 无效 section 正确抛出异常: {e}")

    print()


def test_profile_persistence():
    """测试档案的加载和保存。"""
    print("=" * 50)
    print("测试 2: 档案持久化")
    print("=" * 50)

    # 使用临时目录避免污染真实数据
    import src.tools.profile as profile_module
    original_dir = profile_module.PROFILE_DIR

    with tempfile.TemporaryDirectory() as tmpdir:
        profile_module.PROFILE_DIR = Path(tmpdir)

        # 测试加载不存在的档案
        p = load_profile("test")
        assert p.who == {}
        assert p.version == 0
        print("[PASS] 加载不存在的档案返回空档案")

        # 测试保存和加载
        p.merge("who", {"name": "李四"})
        save_profile(p, "test")
        loaded = load_profile("test")
        assert loaded.who == {"name": "李四"}
        assert loaded.version == 1
        print("[PASS] 保存和加载成功")

        # 测试 merge_section
        result = merge_section("have", '{"skills": ["Java"]}', "test")
        assert result.have == {"skills": ["Java"]}
        assert result.version == 2
        print("[PASS] merge_section JSON 解析成功")

        # 测试非 JSON 数据
        result = merge_section("want", "我想做前端开发", "test")
        assert result.want == {"raw": "我想做前端开发"}
        print("[PASS] merge_section 非 JSON 数据处理成功")

        profile_module.PROFILE_DIR = original_dir

    print()


def test_resume_parser():
    """测试简历解析。"""
    print("=" * 50)
    print("测试 3: 简历解析")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        # 测试 TXT 文件
        txt_path = Path(tmpdir) / "resume.txt"
        txt_path.write_text("张三\n前端工程师\n3年经验", encoding="utf-8")
        text = extract_text(str(txt_path))
        assert "张三" in text
        assert "前端工程师" in text
        print("[PASS] TXT 文件解析成功")

        # 测试 Markdown 文件
        md_path = Path(tmpdir) / "resume.md"
        md_path.write_text("# 张三\n\n## 技能\n- React\n- Vue", encoding="utf-8")
        text = extract_text(str(md_path))
        assert "张三" in text
        assert "React" in text
        print("[PASS] Markdown 文件解析成功")

        # 测试文件不存在
        try:
            extract_text("/nonexistent/file.txt")
            assert False, "应该抛出异常"
        except FileNotFoundError as e:
            print(f"[PASS] 文件不存在正确抛出异常: {e}")

        # 测试不支持的格式
        try:
            bad_path = Path(tmpdir) / "test.xyz"
            bad_path.write_text("test")
            extract_text(str(bad_path))
            assert False, "应该抛出异常"
        except ValueError as e:
            print(f"[PASS] 不支持格式正确抛出异常: {e}")

    print()


def test_session():
    """测试会话启动。"""
    print("=" * 50)
    print("测试 4: 会话启动")
    print("=" * 50)

    msg = get_welcome_message()
    assert "Career Kit" in msg
    assert "简历" in msg
    assert "口述" in msg
    print("[PASS] 欢迎信息包含关键内容")
    print(f"\n欢迎信息预览:\n{msg[:200]}...")
    print()


def test_intake_flow():
    """测试完整的 intake 流程。"""
    print("=" * 50)
    print("测试 5: 完整 intake 流程")
    print("=" * 50)

    import src.tools.profile as profile_module
    original_dir = profile_module.PROFILE_DIR

    with tempfile.TemporaryDirectory() as tmpdir:
        profile_module.PROFILE_DIR = Path(tmpdir)

        # 模拟完整流程
        # 1. 填充 who
        p1 = merge_section("who", '{"name": "王五", "status": "应届生"}')
        assert p1.who["name"] == "王五"
        print("[PASS] intake who 成功")

        # 2. 填充 have
        p2 = merge_section("have", '{"skills": ["Python", "React"], "education": "本科"}')
        assert "Python" in p2.have["skills"]
        print("[PASS] intake have 成功")

        # 3. 填充 want
        p3 = merge_section("want", '{"target_role": "前端工程师", "timeline": "6个月"}')
        assert p3.want["target_role"] == "前端工程师"
        print("[PASS] intake want 成功")

        # 4. 验证档案完整性
        final = load_profile()
        assert final.who["name"] == "王五"
        assert "skills" in final.have
        assert final.want["timeline"] == "6个月"
        assert final.version == 3
        print("[PASS] 档案数据完整")

        profile_module.PROFILE_DIR = original_dir

    print()


def main():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("Career Kit 测试套件")
    print("=" * 60 + "\n")

    tests = [
        test_models_merge,
        test_profile_persistence,
        test_resume_parser,
        test_session,
        test_intake_flow,
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
