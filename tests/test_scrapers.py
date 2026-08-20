"""企业 JD 爬虫框架测试。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src.scrapers.base import CompanyScraper
from src.scrapers.loader import (
    get_scraper,
    list_scrapers,
    search_company_jobs,
    get_job_detail,
    _load_config,
)


# === 模拟 Scraper ===

class MockScraper(CompanyScraper):
    """测试用的模拟 Scraper。"""

    def search(self, **kwargs):
        keyword = kwargs.get("keyword", "")
        return [
            {
                "title": f"{keyword} 工程师",
                "url": "https://example.com/job/1",
                "company": "测试公司",
                "location": "北京",
                "summary": f"负责 {keyword} 相关开发",
            },
            {
                "title": f"高级 {keyword} 工程师",
                "url": "https://example.com/job/2",
                "company": "测试公司",
                "location": "上海",
                "summary": f"负责 {keyword} 架构设计",
            },
        ]

    def get_detail(self, url: str):
        return {
            "title": "AI Agent 开发工程师",
            "company": "测试公司",
            "location": "北京",
            "salary": "30-60k",
            "description": "负责 AI Agent 框架开发",
            "requirements": "熟悉 LangChain, Python",
            "benefits": "六险一金, 弹性工作",
        }


# === 测试函数 ===


def test_scraper_interface():
    """测试 Scraper 接口定义。"""
    print("=" * 60)
    print("测试 1: Scraper 接口")
    print("=" * 60)

    # CompanyScraper 是抽象类，不能直接实例化
    try:
        CompanyScraper()
        assert False, "应该抛出 TypeError"
    except TypeError:
        print("[OK] CompanyScraper 不能直接实例化")

    # MockScraper 可以实例化
    scraper = MockScraper()
    assert isinstance(scraper, CompanyScraper)
    print("[OK] MockScraper 继承成功")

    # search 返回列表
    results = scraper.search(keyword="Python")
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["title"] == "Python 工程师"
    print(f"[OK] search 返回 {len(results)} 个结果")

    # get_detail 返回 dict
    detail = scraper.get_detail("https://example.com/job/1")
    assert isinstance(detail, dict)
    assert detail["title"] == "AI Agent 开发工程师"
    assert detail["salary"] == "30-60k"
    print(f"[OK] get_detail 返回岗位详情")

    print()


def test_config_loading():
    """测试配置加载。"""
    print("=" * 60)
    print("测试 2: 配置加载")
    print("=" * 60)

    config = _load_config()
    assert "scrapers" in config
    print(f"[OK] config.yaml 加载成功")

    scrapers = list_scrapers()
    assert isinstance(scrapers, list)
    assert len(scrapers) >= 1, "至少应有 1 个 Scraper"
    print(f"[OK] 已注册 {len(scrapers)} 个 Scraper")

    # 验证 bytedance 已注册
    ids = [s["id"] for s in scrapers]
    assert "bytedance" in ids, "bytedance 未注册"
    print(f"[OK] bytedance 已注册")

    # 验证参数定义
    bd = next(s for s in scrapers if s["id"] == "bytedance")
    assert "keyword" in bd["params"]
    assert "city" in bd["params"]
    print(f"[OK] bytedance 参数定义正确")
    print()


def test_search_unknown_company():
    """测试搜索未注册的公司。"""
    print("=" * 60)
    print("测试 3: 搜索未注册公司")
    print("=" * 60)

    result = search_company_jobs("nonexistent", keyword="test")
    assert "error" in result
    assert "available" in result
    print(f"[OK] 返回错误信息: {result['error']}")
    print()


def test_get_detail_unknown_url():
    """测试获取未注册 URL 的详情。"""
    print("=" * 60)
    print("测试 4: 获取未知 URL 详情")
    print("=" * 60)

    result = get_job_detail("https://unknown.com/job/1")
    assert "error" in result
    print(f"[OK] 返回错误信息: {result['error']}")
    print()


def test_mcp_tools_registered():
    """测试 MCP tools 注册。"""
    print("=" * 60)
    print("测试 5: MCP Tools 注册")
    print("=" * 60)

    from src.server import mcp

    tools = {t.name for t in mcp._tool_manager.list_tools()}

    expected = ["list_company_jobs", "fetch_company_jobs", "fetch_jd_detail"]
    for t in expected:
        assert t in tools, f"{t} 未注册"
        print(f"[OK] {t} 已注册")

    print(f"\n共注册 {len(tools)} 个 MCP tools")
    print()


def test_mock_scraper_integration():
    """测试 MockScraper 完整流程。"""
    print("=" * 60)
    print("测试 6: MockScraper 集成")
    print("=" * 60)

    # 直接调用 MockScraper（不通过 loader，因为 config 里没注册）
    scraper = MockScraper()

    # 搜索
    results = scraper.search(keyword="AI Agent")
    assert len(results) == 2
    print(f"[OK] 搜索返回 {len(results)} 个岗位")

    # 详情
    detail = scraper.get_detail(results[0]["url"])
    assert "description" in detail
    assert "requirements" in detail
    print(f"[OK] 详情包含描述和要求")

    # 验证字段规范
    for field in ["title", "url", "company", "location", "summary"]:
        assert field in results[0], f"search 结果缺少 {field}"
    print(f"[OK] search 字段规范正确")

    for field in ["title", "company", "description", "requirements"]:
        assert field in detail, f"get_detail 结果缺少 {field}"
    print(f"[OK] get_detail 字段规范正确")

    print()


def main():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("企业 JD 爬虫框架测试套件")
    print("=" * 60 + "\n")

    tests = [
        test_scraper_interface,
        test_config_loading,
        test_search_unknown_company,
        test_get_detail_unknown_url,
        test_mcp_tools_registered,
        test_mock_scraper_integration,
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
