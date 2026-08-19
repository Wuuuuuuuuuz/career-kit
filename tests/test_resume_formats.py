"""简历格式测试——用真实简历文件测试解析功能。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.resume_parser import extract_text

TEST_DIR = Path(__file__).parent.parent / "dev" / "test"


def test_markdown():
    """测试 Markdown 简历解析。"""
    print("=" * 60)
    print("测试 1: Markdown 简历")
    print("=" * 60)

    md_file = TEST_DIR / "AI.md"
    if not md_file.exists():
        print("[SKIP] AI.md 不存在")
        return

    text = extract_text(str(md_file))
    print(f"[OK] 提取成功，共 {len(text)} 字符")
    print(f"\n前 500 字符预览:\n{'-' * 40}")
    print(text[:500])
    print(f"{'-' * 40}\n")
    return text


def test_docx():
    """测试 DOCX 简历解析。"""
    print("=" * 60)
    print("测试 2: DOCX 简历")
    print("=" * 60)

    docx_file = TEST_DIR / "AI岗.docx"
    if not docx_file.exists():
        print("[SKIP] AI岗.docx 不存在")
        return

    text = extract_text(str(docx_file))
    print(f"[OK] 提取成功，共 {len(text)} 字符")
    print(f"\n前 500 字符预览:\n{'-' * 40}")
    print(text[:500])
    print(f"{'-' * 40}\n")
    return text


def test_pdf():
    """测试 PDF 简历解析。"""
    print("=" * 60)
    print("测试 3: PDF 简历")
    print("=" * 60)

    pdf_file = TEST_DIR / "AI岗.pdf"
    if not pdf_file.exists():
        print("[SKIP] AI岗.pdf 不存在")
        return

    text = extract_text(str(pdf_file))
    print(f"[OK] 提取成功，共 {len(text)} 字符")
    print(f"\n前 500 字符预览:\n{'-' * 40}")
    print(text[:500])
    print(f"{'-' * 40}\n")
    return text


def compare_results(md_text, docx_text, pdf_text):
    """比较三种格式的解析结果。"""
    print("=" * 60)
    print("比较分析")
    print("=" * 60)

    results = {
        "Markdown": md_text,
        "DOCX": docx_text,
        "PDF": pdf_text,
    }

    for name, text in results.items():
        if text:
            print(f"{name}: {len(text)} 字符")

    # 检查是否包含关键信息
    keywords = ["AI", "经验", "技能", "项目"]
    print("\n关键信息提取检查:")
    for kw in keywords:
        found_in = []
        for name, text in results.items():
            if text and kw in text:
                found_in.append(name)
        if found_in:
            print(f"  '{kw}': {', '.join(found_in)}")
        else:
            print(f"  '{kw}': 未找到")


def main():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("简历格式解析测试")
    print("=" * 60 + "\n")

    md_text = test_markdown()
    docx_text = test_docx()
    pdf_text = test_pdf()

    if any([md_text, docx_text, pdf_text]):
        compare_results(md_text, docx_text, pdf_text)

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
