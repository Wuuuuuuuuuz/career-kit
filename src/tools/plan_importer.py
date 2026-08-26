"""计划导入——解析用户的既有规划文档。

对比、合并、取舍在 LLM 对话中完成；落盘统一走 save_roadmap。
"""

from __future__ import annotations

import re

from .resume_parser import extract_text

# 除换行/制表外的控制字符（\x00-\x08, \x0b, \x0c, \x0e-\x1f）
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def parse_plan_file(file_path: str) -> str:
    """解析计划文件，返回清洗后的纯文本。复用 resume_parser。

    二进制垃圾 / 大量控制字符的内容直接拒绝（OBS-003），
    不把垃圾字节透传给上层 LLM 做 diff。

    Raises:
        ValueError: 文件不可读或内容为空
    """
    text = extract_text(file_path)
    cleaned = _CONTROL_CHARS.sub("", text)

    if not cleaned.strip():
        raise ValueError(f"文件内容为空或不可读：{file_path}")

    control_ratio = 1 - (len(cleaned) / len(text)) if text else 1.0
    if control_ratio > 0.05:
        raise ValueError(
            f"文件包含大量控制字符（{control_ratio:.0%}），疑似二进制文件而非文本计划：{file_path}"
        )
    return cleaned
