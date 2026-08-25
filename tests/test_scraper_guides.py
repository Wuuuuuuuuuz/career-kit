"""scraper 使用指南完整性测试。

约定：每个注册在 config.yaml 的企业数据源，必须在其包目录内提供
guide.md 使用教程（LLM 通过 get_scraper_guide 按需读取）。
贡献新 scraper 时从 _template/guide.md 复制填写，本测试保证不漏。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

SCRAPERS_DIR = Path(__file__).parent.parent / "src" / "scrapers"


def _registered_company_ids() -> list[str]:
    from src.scrapers.loader import list_scrapers

    return [s["id"] for s in list_scrapers()]


def test_every_registered_scraper_has_guide():
    """每个已注册的企业源必须附带 guide.md。"""
    ids = _registered_company_ids()
    assert ids, "config.yaml 中没有注册任何 scraper"

    missing = [
        cid for cid in ids if not (SCRAPERS_DIR / cid / "guide.md").exists()
    ]
    assert not missing, f"以下企业源缺少 guide.md：{missing}（模板见 src/scrapers/_template/guide.md）"


def test_guides_have_required_sections():
    """guide.md 必须包含核心章节，保证 LLM 能按需取到关键信息。"""
    required = ["## 用途", "## 参数", "## 调用示例", "## 返回字段"]
    for cid in _registered_company_ids():
        content = (SCRAPERS_DIR / cid / "guide.md").read_text(encoding="utf-8")
        absent = [sec for sec in required if sec not in content]
        assert not absent, f"{cid}/guide.md 缺少章节：{absent}"


def test_get_scraper_guide_tool():
    """get_scraper_guide 对已知源返回教程内容，未知源返回可用列表。"""
    from src.server import get_scraper_guide

    for cid in _registered_company_ids():
        result = get_scraper_guide(company=cid)
        assert isinstance(result, str)
        assert len(result) > 100, f"{cid} 的指南内容过短"
        assert "没有使用指南" not in result

    result = get_scraper_guide(company="nonexistent")
    assert isinstance(result, str)
    assert "可用数据源" in result


def test_every_registered_scraper_declares_params():
    """每个已注册的企业源必须在类上声明 PARAMS（参数唯一事实源）。

    config.yaml 不再维护参数——list_data_sources 直接渲染类上的 PARAMS。
    """
    from src.scrapers.loader import get_scraper

    for cid in _registered_company_ids():
        scraper = get_scraper(cid)
        assert scraper is not None, f"{cid} 无法实例化"
        params = getattr(scraper, "PARAMS", None)
        assert isinstance(params, dict) and params, (
            f"{cid} 未声明 PARAMS 类属性（应包含 required/description），"
            f"参考 _template/scraper.py"
        )
        for pname, pinfo in params.items():
            assert isinstance(pinfo, dict) and "description" in pinfo, (
                f"{cid}.PARAMS['{pname}'] 缺少 description"
            )


def test_knowledge_writer_does_not_mutate_input():
    """知识库写入不得污染调用方的原始结果 dict（写入到临时目录验证）。"""
    import tempfile

    import src.scrapers.knowledge_writer as kw
    from src.tools.knowledge_search import search_knowledge  # noqa: F401  确保模块可导入

    with tempfile.TemporaryDirectory() as tmp:
        original_dir = kw.KNOWLEDGE_DIR
        kw.KNOWLEDGE_DIR = Path(tmp)
        try:
            original = {"title": "测试岗位", "url": "https://example.com/x"}
            payload = dict(original)
            result = kw.write_to_knowledge("testcompany.scraper", [payload], data_type="jds")

            assert result == 1
            # 原始 dict 不被污染
            assert "_fetched_at" not in payload
            assert "_source" not in payload
            assert payload == original
        finally:
            kw.KNOWLEDGE_DIR = original_dir
