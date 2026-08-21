"""知识库写入器单元测试。

测试 write_to_knowledge() 及相关函数的文件写入、文件名生成、元数据添加等逻辑。
使用 tmp_path fixture 隔离文件系统，不产生真实副作用。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.knowledge_writer import (
    _format_interview_markdown,
    _generate_filename,
    _generate_interview_filename,
    _sanitize_filename,
    write_interview_to_knowledge,
    write_to_knowledge,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_knowledge_dir(tmp_path, monkeypatch):
    """将 KNOWLEDGE_DIR 重定向到临时目录，避免污染真实知识库。"""
    import src.scrapers.knowledge_writer as kw

    monkeypatch.setattr(kw, "KNOWLEDGE_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# _sanitize_filename
# ---------------------------------------------------------------------------


class TestSanitizeFilename:
    """文件名清理函数测试。"""

    def test_normal_text(self):
        assert _sanitize_filename("Python工程师") == "Python工程师"

    def test_special_characters_replaced(self):
        result = _sanitize_filename("C++/Go 工程师")
        assert "/" not in result
        assert " " not in result
        # 下划线连接
        assert "__" not in result

    def test_multiple_underscores_collapsed(self):
        result = _sanitize_filename("a___b___c")
        assert "__" not in result
        assert result == "a_b_c"

    def test_leading_trailing_underscores_stripped(self):
        result = _sanitize_filename("_hello_")
        assert result == "hello"

    def test_length_limit(self):
        long_text = "A" * 100
        result = _sanitize_filename(long_text)
        assert len(result) <= 50

    def test_empty_string_returns_unknown(self):
        assert _sanitize_filename("") == "unknown"
        assert _sanitize_filename("___") == "unknown"

    def test_only_special_chars(self):
        result = _sanitize_filename("@#$%^&")
        # 只剩下下划线，清理后为空 → unknown
        assert result == "unknown"


# ---------------------------------------------------------------------------
# _generate_filename
# ---------------------------------------------------------------------------


class TestGenerateFilename:
    """JD 文件名生成测试。"""

    def test_basic_format(self):
        item = {"title": "Python工程师", "location": "北京"}
        filename = _generate_filename(item, "bytedance")
        today = datetime.now().strftime("%Y-%m-%d")
        assert filename.startswith(today)
        assert filename.endswith(".json")
        assert "Python工程师" in filename

    def test_location_first_city_only(self):
        item = {"title": "开发", "location": "北京、上海、深圳"}
        filename = _generate_filename(item, "test")
        assert "北京" in filename
        assert "上海" not in filename

    def test_no_location(self):
        item = {"title": "开发"}
        filename = _generate_filename(item, "test")
        today = datetime.now().strftime("%Y-%m-%d")
        # 格式: {date}_{title}.json
        assert filename == f"{today}_开发.json"

    def test_missing_title(self):
        item = {}
        filename = _generate_filename(item, "test")
        today = datetime.now().strftime("%Y-%m-%d")
        assert filename == f"{today}_unknown.json"

    def test_empty_location_string(self):
        item = {"title": "开发", "location": ""}
        filename = _generate_filename(item, "test")
        today = datetime.now().strftime("%Y-%m-%d")
        assert filename == f"{today}_开发.json"


# ---------------------------------------------------------------------------
# write_to_knowledge — JD 数据写入
# ---------------------------------------------------------------------------


class TestWriteToKnowledge:
    """write_to_knowledge() 核心逻辑测试。"""

    def test_write_single_dict(self, tmp_path):
        data = {"title": "AI工程师", "location": "北京", "salary": "30-60k"}
        count = write_to_knowledge("bytedance.scraper", data)
        assert count == 1

        # 验证文件存在
        target_dir = tmp_path / "jds" / "bytedance"
        assert target_dir.exists()
        files = list(target_dir.glob("*.json"))
        assert len(files) == 1

    def test_write_list_of_dicts(self, tmp_path):
        data = [
            {"title": "前端工程师", "location": "上海"},
            {"title": "后端工程师", "location": "北京"},
        ]
        count = write_to_knowledge("bytedance.scraper", data)
        assert count == 2

        target_dir = tmp_path / "jds" / "bytedance"
        files = list(target_dir.glob("*.json"))
        assert len(files) == 2

    def test_skip_error_items(self, tmp_path):
        data = [
            {"title": "正常岗位", "location": "北京"},
            {"error": "抓取失败"},
            {"title": "另一个岗位", "location": "上海"},
        ]
        count = write_to_knowledge("bytedance.scraper", data)
        assert count == 2

    def test_skip_none_items(self, tmp_path):
        data = [None, {"title": "正常岗位"}]
        count = write_to_knowledge("bytedance.scraper", data)
        assert count == 1

    def test_skip_empty_dict(self, tmp_path):
        data = [{}, {"title": "正常岗位"}]
        count = write_to_knowledge("bytedance.scraper", data)
        assert count == 1

    def test_metadata_added(self, tmp_path):
        data = {"title": "测试岗位", "location": "深圳"}
        write_to_knowledge("bytedance.scraper", data)

        target_dir = tmp_path / "jds" / "bytedance"
        files = list(target_dir.glob("*.json"))
        assert len(files) == 1

        content = json.loads(files[0].read_text(encoding="utf-8"))
        assert "_fetched_at" in content
        assert "_source" in content
        assert content["_source"] == "bytedance"

        # _fetched_at 应为合法 ISO 格式
        datetime.fromisoformat(content["_fetched_at"])

    def test_company_name_extracted_from_module(self, tmp_path):
        """公司名从模块路径第一段提取。"""
        data = {"title": "测试"}
        write_to_knowledge("tencent.hr.scraper", data)

        target_dir = tmp_path / "jds" / "tencent"
        assert target_dir.exists()

    def test_json_content_valid(self, tmp_path):
        data = {"title": "测试", "description": "包含中文和特殊字符 <>&\""}
        write_to_knowledge("bytedance.scraper", data)

        target_dir = tmp_path / "jds" / "bytedance"
        files = list(target_dir.glob("*.json"))
        content = json.loads(files[0].read_text(encoding="utf-8"))
        assert content["description"] == data["description"]

    def test_custom_data_type(self, tmp_path):
        data = {"title": "市场数据"}
        write_to_knowledge("bytedance.scraper", data, data_type="market")

        target_dir = tmp_path / "market" / "bytedance"
        assert target_dir.exists()
        assert len(list(target_dir.glob("*.json"))) == 1

    def test_empty_list_returns_zero(self, tmp_path):
        count = write_to_knowledge("bytedance.scraper", [])
        assert count == 0

    def test_original_data_preserved(self, tmp_path):
        """原始字段在写入后仍然保留。"""
        data = {"title": "测试", "salary": "30k", "tags": ["AI", "Python"]}
        write_to_knowledge("bytedance.scraper", data)

        target_dir = tmp_path / "jds" / "bytedance"
        files = list(target_dir.glob("*.json"))
        content = json.loads(files[0].read_text(encoding="utf-8"))
        assert content["title"] == "测试"
        assert content["salary"] == "30k"
        assert content["tags"] == ["AI", "Python"]


# ---------------------------------------------------------------------------
# write_interview_to_knowledge — 面经数据写入
# ---------------------------------------------------------------------------


class TestWriteInterviewToKnowledge:
    """面经写入测试。"""

    def test_write_single_interview(self, tmp_path):
        data = {
            "company": "字节跳动",
            "position": "后端工程师",
            "round": "一面",
            "date": "2025-01-15",
            "content": "问了操作系统和网络",
        }
        count = write_interview_to_knowledge("nowcoder", data)
        assert count == 1

        target_dir = tmp_path / "interviews" / "nowcoder"
        assert target_dir.exists()
        files = list(target_dir.glob("*.md"))
        assert len(files) == 1

    def test_interview_markdown_format(self, tmp_path):
        data = {
            "company": "阿里巴巴",
            "position": "前端工程师",
            "round": "二面",
            "date": "2025-03-10",
            "content": "React 原理和性能优化",
            "tags": ["React", "性能"],
        }
        write_interview_to_knowledge("nowcoder", data)

        target_dir = tmp_path / "interviews" / "nowcoder"
        md_file = list(target_dir.glob("*.md"))[0]
        content = md_file.read_text(encoding="utf-8")

        assert "---" in content  # frontmatter
        assert "company: 阿里巴巴" in content
        assert "## 阿里巴巴 - 前端工程师" in content
        assert "**轮次**：二面" in content
        assert "React 原理和性能优化" in content
        assert "React" in content

    def test_interview_filename_format(self, tmp_path):
        data = {
            "company": "腾讯",
            "position": "算法工程师",
            "round": "三面",
            "date": "2025-06-01",
            "content": "手撕代码",
        }
        write_interview_to_knowledge("xiaohongshu", data)

        target_dir = tmp_path / "interviews" / "xiaohongshu"
        files = list(target_dir.glob("*.md"))
        filename = files[0].name
        # 格式: {company}_{position}_{round}_{date}.md
        assert filename.endswith(".md")
        assert "腾讯" in filename
        assert "2025-06-01" in filename

    def test_skip_error_interview(self, tmp_path):
        data = [
            {"company": "A", "content": "正常面经"},
            {"error": "解析失败"},
        ]
        count = write_interview_to_knowledge("nowcoder", data)
        assert count == 1

    def test_interview_no_content_placeholder(self, tmp_path):
        data = {
            "company": "测试公司",
            "position": "开发",
            "date": "2025-01-01",
        }
        write_interview_to_knowledge("nowcoder", data)

        target_dir = tmp_path / "interviews" / "nowcoder"
        md_file = list(target_dir.glob("*.md"))[0]
        content = md_file.read_text(encoding="utf-8")
        assert "待补充面试内容" in content


# ---------------------------------------------------------------------------
# _generate_interview_filename
# ---------------------------------------------------------------------------


class TestGenerateInterviewFilename:
    """面经文件名生成测试。"""

    def test_full_fields(self):
        item = {
            "company": "字节跳动",
            "position": "后端",
            "round": "一面",
            "date": "2025-01-15",
        }
        filename = _generate_interview_filename(item, "nowcoder")
        assert filename.endswith(".md")
        assert "字节跳动" in filename
        assert "后端" in filename
        assert "一面" in filename
        assert "2025-01-15" in filename

    def test_minimal_fields(self):
        item = {}
        filename = _generate_interview_filename(item, "nowcoder")
        assert filename.endswith(".md")
        assert "unknown" in filename

    def test_no_round(self):
        item = {"company": "腾讯", "position": "开发", "date": "2025-01-01"}
        filename = _generate_interview_filename(item, "test")
        assert "腾讯" in filename
        # round 为空时不应有多余下划线
        parts = filename.replace(".md", "").split("_")
        # 不应有空字符串部分
        assert all(parts)


# ---------------------------------------------------------------------------
# _format_interview_markdown
# ---------------------------------------------------------------------------


class TestFormatInterviewMarkdown:
    """面经 Markdown 格式化测试。"""

    def test_frontmatter_present(self):
        item = {"company": "A", "position": "B", "date": "2025-01-01"}
        md = _format_interview_markdown(item)
        lines = md.split("\n")
        assert lines[0] == "---"
        # 找到第二个 ---
        closing = next(i for i, l in enumerate(lines[1:], 1) if l == "---")
        assert closing > 0

    def test_content_section(self):
        item = {"company": "A", "position": "B", "content": "详细内容"}
        md = _format_interview_markdown(item)
        assert "## 面试内容" in md
        assert "详细内容" in md

    def test_tags_in_frontmatter(self):
        item = {
            "company": "A",
            "position": "B",
            "tags": ["Python", "算法"],
            "date": "2025-01-01",
        }
        md = _format_interview_markdown(item)
        assert "Python" in md
        assert "算法" in md
