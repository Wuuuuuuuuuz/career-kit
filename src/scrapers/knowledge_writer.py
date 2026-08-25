"""知识库写入器 — 框架自动调用，贡献者无需关心。

将 scraper 抓取的数据自动写入 data/knowledge/ 目录，
实现"抓取即积累"的设计理念。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

# 知识库根目录
KNOWLEDGE_DIR = Path(__file__).parent.parent.parent / "data" / "knowledge"


def write_to_knowledge(
    company_module: str,
    data: list[dict[str, Any]] | dict[str, Any],
    data_type: str = "jds",
) -> int:
    """将抓取数据写入知识库。

    框架自动调用此函数，贡献者无需手动处理。

    Args:
        company_module: 公司模块名（如 "bytedance.scraper"）
        data: 抓取的数据（单个 dict 或 list）
        data_type: 数据类型
            - jds: 岗位描述（JSON 格式）
            - interviews: 面经（Markdown 格式，自动调用 write_interview_to_knowledge）
            - market: 市场数据

    Returns:
        写入的文件数量
    """
    # 提取公司名（跳过 src.scrapers 前缀）
    parts = company_module.split(".")
    if len(parts) >= 3 and parts[0] == "src" and parts[1] == "scrapers":
        company_name = parts[2]
    elif len(parts) >= 2:
        company_name = parts[0]
    else:
        company_name = parts[0]

    # 面经类型走专用写入器
    if data_type == "interviews":
        return write_interview_to_knowledge(company_name, data)

    # 确定目标目录
    target_dir = KNOWLEDGE_DIR / data_type / company_name
    target_dir.mkdir(parents=True, exist_ok=True)

    # 统一转为 list
    if isinstance(data, dict):
        data = [data]

    count = 0
    for item in data:
        if not item or item.get("error"):
            continue

        # 生成文件名
        filename = _generate_filename(item, company_name)
        filepath = target_dir / filename

        # 添加元数据（写入副本，不污染调用方返回给 LLM 的原始结果）
        payload = {**item, "_fetched_at": datetime.now().isoformat(), "_source": company_name}

        # 写入文件
        try:
            filepath.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            count += 1
        except Exception:
            continue

    return count


def write_interview_to_knowledge(
    source: str,
    data: list[dict[str, Any]] | dict[str, Any],
) -> int:
    """将面经数据写入知识库。

    面经使用 Markdown 格式，便于阅读和检索。

    Args:
        source: 数据来源（如 "nowcoder", "xiaohongshu"）
        data: 面经数据

    Returns:
        写入的文件数量
    """
    target_dir = KNOWLEDGE_DIR / "interviews" / source
    target_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(data, dict):
        data = [data]

    count = 0
    for item in data:
        if not item or item.get("error"):
            continue

        # 生成 Markdown 内容
        md_content = _format_interview_markdown(item)
        filename = _generate_interview_filename(item, source)
        filepath = target_dir / filename

        try:
            filepath.write_text(md_content, encoding="utf-8")
            count += 1
        except Exception:
            continue

    return count


def _generate_filename(item: dict, company_name: str) -> str:
    """生成 JD 文件名。

    格式：{date}_{title}_{city}.json
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    title = _sanitize_filename(item.get("title", "unknown"))
    city = item.get("location", "").split("、")[0]  # 取第一个城市
    city = _sanitize_filename(city) if city else ""

    parts = [date_str, title]
    if city:
        parts.append(city)

    return "_".join(parts) + ".json"


def _generate_interview_filename(item: dict, source: str) -> str:
    """生成面经文件名。

    格式：{company}_{position}_{round}_{date}.md
    """
    company = _sanitize_filename(item.get("company", "unknown"))
    position = _sanitize_filename(item.get("position", ""))
    round_name = _sanitize_filename(item.get("round", ""))
    date_str = item.get("date", datetime.now().strftime("%Y-%m-%d"))

    parts = [company]
    if position:
        parts.append(position)
    if round_name:
        parts.append(round_name)
    parts.append(date_str)

    return "_".join(parts) + ".md"


def _format_interview_markdown(item: dict) -> str:
    """将面经数据格式化为 Markdown。"""
    company = item.get("company", "未知公司")
    position = item.get("position", "未知岗位")
    round_name = item.get("round", "")
    date = item.get("date", datetime.now().strftime("%Y-%m-%d"))
    source = item.get("source", "")
    url = item.get("url", "")
    content = item.get("content", "")
    tags = item.get("tags", [])

    lines = [
        "---",
        f"source: {source}",
        f"url: {url}",
        f"company: {company}",
        f"position: {position}",
        f"round: {round_name}",
        f"date: {date}",
        f"tags: [{', '.join(tags)}]",
        "---",
        "",
        f"## {company} - {position}",
        "",
    ]

    if round_name:
        lines.append(f"**轮次**：{round_name}")
    if date:
        lines.append(f"**日期**：{date}")
    lines.append("")

    if content:
        lines.append("## 面试内容")
        lines.append("")
        lines.append(content)
    else:
        lines.append("*（待补充面试内容）*")

    return "\n".join(lines)


def _sanitize_filename(text: str) -> str:
    """清理文件名，移除特殊字符。"""
    # 只保留中文、英文、数字、下划线
    text = re.sub(r'[^\w一-鿿]', '_', text)
    # 合并多个下划线
    text = re.sub(r'_+', '_', text)
    # 去除首尾下划线
    text = text.strip('_')
    # 限制长度
    if len(text) > 50:
        text = text[:50]
    return text or "unknown"
