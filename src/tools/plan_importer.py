"""计划导入——解析用户的既有规划文档。

对比、合并、取舍在 LLM 对话中完成；落盘统一走 save_roadmap。
"""

from __future__ import annotations

from .resume_parser import extract_text


def parse_plan_file(file_path: str) -> str:
    """解析计划文件，返回纯文本。复用 resume_parser。

    Args:
        file_path: 计划文件的绝对路径

    Returns:
        提取的文本内容
    """
    return extract_text(file_path)
