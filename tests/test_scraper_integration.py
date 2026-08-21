"""Scraper + 知识库集成测试。

验证 scraper 调用后数据能自动写入知识库，且文件内容格式正确。
全部使用 mock，不发起真实网络请求。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.base import CompanyScraper
from src.scrapers.knowledge_writer import write_interview_to_knowledge, write_to_knowledge


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_knowledge_dir(tmp_path, monkeypatch):
    """将 KNOWLEDGE_DIR 重定向到临时目录。"""
    import src.scrapers.knowledge_writer as kw

    monkeypatch.setattr(kw, "KNOWLEDGE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def mock_jd_results():
    """模拟 scraper.search() 返回的 JD 列表。"""
    return [
        {
            "title": "AI Agent 开发工程师",
            "url": "https://jobs.bytedance.com/123",
            "company": "字节跳动",
            "location": "北京",
            "department": "AI Lab",
            "summary": "负责 AI Agent 框架研发",
        },
        {
            "title": "大模型算法工程师",
            "url": "https://jobs.bytedance.com/456",
            "company": "字节跳动",
            "location": "上海",
            "department": "AI Lab",
            "summary": "负责大模型训练与推理优化",
        },
    ]


@pytest.fixture
def mock_jd_detail():
    """模拟 scraper.get_detail() 返回的 JD 详情。"""
    return {
        "title": "AI Agent 开发工程师",
        "company": "字节跳动",
        "location": "北京",
        "salary": "30-60k",
        "description": "负责 AI Agent 框架研发，参与核心模块设计与实现",
        "requirements": "1. 熟悉 Python\n2. 了解 LLM 原理\n3. 有 Agent 开发经验优先",
        "benefits": "六险一金、弹性工作、免费三餐",
    }


@pytest.fixture
def mock_interview_data():
    """模拟面经数据。"""
    return [
        {
            "company": "字节跳动",
            "position": "后端工程师",
            "round": "一面",
            "date": "2025-06-15",
            "source": "nowcoder",
            "url": "https://www.nowcoder.com/discuss/123",
            "content": "1. 自我介绍\n2. 项目经历\n3. 手撕 LRU Cache",
            "tags": ["后端", "字节跳动", "一面"],
        },
        {
            "company": "字节跳动",
            "position": "后端工程师",
            "round": "二面",
            "date": "2025-06-20",
            "source": "nowcoder",
            "url": "https://www.nowcoder.com/discuss/456",
            "content": "1. 系统设计：短链接服务\n2. 分布式一致性问题",
            "tags": ["后端", "字节跳动", "二面", "系统设计"],
        },
    ]


# ---------------------------------------------------------------------------
# 集成测试：Scraper → 知识库写入
# ---------------------------------------------------------------------------


class TestScraperToKnowledgeIntegration:
    """测试 scraper 搜索结果自动写入知识库的完整流程。"""

    def test_search_results_written_to_knowledge(self, tmp_path, mock_jd_results):
        """scraper.search() 结果通过 write_to_knowledge 写入文件。"""
        count = write_to_knowledge("bytedance.scraper", mock_jd_results)
        assert count == 2

        target_dir = tmp_path / "jds" / "bytedance"
        assert target_dir.exists()
        files = list(target_dir.glob("*.json"))
        assert len(files) == 2

    def test_written_jd_content_has_all_fields(self, tmp_path, mock_jd_results):
        """写入的 JD 文件包含原始字段 + 元数据。"""
        write_to_knowledge("bytedance.scraper", mock_jd_results)

        target_dir = tmp_path / "jds" / "bytedance"
        for f in target_dir.glob("*.json"):
            content = json.loads(f.read_text(encoding="utf-8"))
            # 原始字段
            assert "title" in content
            assert "url" in content
            assert "company" in content
            # 元数据
            assert "_fetched_at" in content
            assert "_source" in content
            assert content["_source"] == "bytedance"

    def test_jd_detail_written_to_knowledge(self, tmp_path, mock_jd_detail):
        """单个 JD 详情也能正确写入。"""
        count = write_to_knowledge("bytedance.scraper", mock_jd_detail)
        assert count == 1

        target_dir = tmp_path / "jds" / "bytedance"
        files = list(target_dir.glob("*.json"))
        content = json.loads(files[0].read_text(encoding="utf-8"))

        assert content["title"] == "AI Agent 开发工程师"
        assert content["salary"] == "30-60k"
        assert "requirements" in content
        assert "benefits" in content

    def test_written_json_is_valid_and_pretty(self, tmp_path, mock_jd_results):
        """写入的 JSON 格式正确（带缩进，UTF-8）。"""
        write_to_knowledge("bytedance.scraper", mock_jd_results)

        target_dir = tmp_path / "jds" / "bytedance"
        for f in target_dir.glob("*.json"):
            raw = f.read_text(encoding="utf-8")
            # 带缩进的 JSON 应包含换行
            assert "\n" in raw
            # 能被 json.loads 正确解析
            parsed = json.loads(raw)
            assert isinstance(parsed, dict)

    def test_chinese_content_preserved(self, tmp_path):
        """中文内容在写入/读取过程中不丢失。"""
        data = {
            "title": "高级算法工程师",
            "description": "负责自然语言处理、计算机视觉等方向的算法研发与落地",
            "requirements": "博士学历优先，有顶会论文发表经验",
        }
        write_to_knowledge("bytedance.scraper", data)

        target_dir = tmp_path / "jds" / "bytedance"
        f = list(target_dir.glob("*.json"))[0]
        content = json.loads(f.read_text(encoding="utf-8"))
        assert content["title"] == "高级算法工程师"
        assert "自然语言处理" in content["description"]


# ---------------------------------------------------------------------------
# 集成测试：面经数据写入
# ---------------------------------------------------------------------------


class TestInterviewToKnowledgeIntegration:
    """面经数据写入知识库的集成测试。"""

    def test_interviews_written_as_markdown(self, tmp_path, mock_interview_data):
        """面经数据以 Markdown 格式写入。"""
        count = write_interview_to_knowledge("nowcoder", mock_interview_data)
        assert count == 2

        target_dir = tmp_path / "interviews" / "nowcoder"
        md_files = list(target_dir.glob("*.md"))
        assert len(md_files) == 2

    def test_interview_markdown_structure(self, tmp_path, mock_interview_data):
        """验证面经 Markdown 的结构完整性。"""
        write_interview_to_knowledge("nowcoder", mock_interview_data)

        target_dir = tmp_path / "interviews" / "nowcoder"
        for f in target_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            # frontmatter
            assert content.startswith("---")
            # 包含公司名
            assert "字节跳动" in content
            # 包含岗位
            assert "后端工程师" in content
            # 包含面试内容
            assert "## 面试内容" in content

    def test_interview_tags_in_output(self, tmp_path, mock_interview_data):
        """面经标签写入 frontmatter。"""
        write_interview_to_knowledge("nowcoder", mock_interview_data)

        target_dir = tmp_path / "interviews" / "nowcoder"
        files = sorted(target_dir.glob("*.md"))
        # 第一个面经
        content = files[0].read_text(encoding="utf-8")
        assert "后端" in content
        assert "字节跳动" in content


# ---------------------------------------------------------------------------
# 集成测试：Mock Scraper 完整流程
# ---------------------------------------------------------------------------


class TestMockScraperFullFlow:
    """使用 MockScraper 模拟完整的搜索→写入流程。"""

    def test_search_and_write_flow(self, tmp_path, mock_jd_results):
        """模拟 scraper 搜索后调用 write_to_knowledge 写入。"""
        # 模拟 scraper.search()
        mock_scraper = MagicMock(spec=CompanyScraper)
        mock_scraper.search.return_value = mock_jd_results

        # 执行搜索
        results = mock_scraper.search(keyword="AI")
        assert len(results) == 2

        # 写入知识库
        count = write_to_knowledge("bytedance.scraper", results)
        assert count == 2

        # 验证文件
        target_dir = tmp_path / "jds" / "bytedance"
        files = list(target_dir.glob("*.json"))
        assert len(files) == 2

        titles = set()
        for f in files:
            content = json.loads(f.read_text(encoding="utf-8"))
            titles.add(content["title"])
            # 验证元数据
            assert "_fetched_at" in content
            assert "_source" in content

        assert "AI Agent 开发工程师" in titles
        assert "大模型算法工程师" in titles

    def test_get_detail_and_write_flow(self, tmp_path, mock_jd_detail):
        """模拟 scraper.get_detail() 后写入详情。"""
        mock_scraper = MagicMock(spec=CompanyScraper)
        mock_scraper.get_detail.return_value = mock_jd_detail

        detail = mock_scraper.get_detail("https://jobs.bytedance.com/123")
        count = write_to_knowledge("bytedance.scraper", detail)
        assert count == 1

        target_dir = tmp_path / "jds" / "bytedance"
        f = list(target_dir.glob("*.json"))[0]
        content = json.loads(f.read_text(encoding="utf-8"))

        assert content["title"] == "AI Agent 开发工程师"
        assert content["salary"] == "30-60k"
        assert "requirements" in content

    def test_multiple_companies_isolated(self, tmp_path, mock_jd_results):
        """不同公司的数据写入不同子目录。"""
        # 写入 bytedance
        count_bd = write_to_knowledge("bytedance.scraper", mock_jd_results)
        # 写入 tencent
        tencent_data = [{"title": "游戏开发", "location": "深圳"}]
        count_tx = write_to_knowledge("tencent.scraper", tencent_data)

        assert count_bd == 2
        assert count_tx == 1

        bd_dir = tmp_path / "jds" / "bytedance"
        tx_dir = tmp_path / "jds" / "tencent"
        assert bd_dir.exists()
        assert tx_dir.exists()
        assert len(list(bd_dir.glob("*.json"))) == 2
        assert len(list(tx_dir.glob("*.json"))) == 1

    def test_search_returns_error_not_written(self, tmp_path):
        """包含 error 字典的结果不写入。"""
        results = [
            {"title": "正常岗位", "location": "北京"},
            {"error": "抓取超时"},
        ]
        count = write_to_knowledge("bytedance.scraper", results)
        assert count == 1

        target_dir = tmp_path / "jds" / "bytedance"
        files = list(target_dir.glob("*.json"))
        assert len(files) == 1
        content = json.loads(files[0].read_text(encoding="utf-8"))
        assert "error" not in content

    def test_empty_search_results(self, tmp_path):
        """空搜索结果不创建文件。"""
        count = write_to_knowledge("bytedance.scraper", [])
        assert count == 0

        target_dir = tmp_path / "jds" / "bytedance"
        # 目录被创建但没有文件
        assert target_dir.exists()
        assert len(list(target_dir.glob("*.json"))) == 0
