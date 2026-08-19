"""计划导入与对比分析。"""

from __future__ import annotations

from typing import Any

from .resume_parser import extract_text


def parse_plan_file(file_path: str) -> str:
    """解析计划文件，返回纯文本。复用 resume_parser。

    Args:
        file_path: 计划文件的绝对路径

    Returns:
        提取的文本内容
    """
    return extract_text(file_path)


def compare_plans(old_plan: dict[str, Any], new_plan: dict[str, Any]) -> dict[str, Any]:
    """对比新旧计划，返回差异报告。

    Args:
        old_plan: 旧计划 dict
        new_plan: 新计划 dict

    Returns:
        差异报告，格式：
        {
            "added": [{"key": ..., "value": ...}],
            "removed": [{"key": ..., "value": ...}],
            "modified": [{"key": ..., "old": ..., "new": ...}],
            "unchanged": [{"key": ..., "value": ...}]
        }
    """
    result = {
        "added": [],
        "removed": [],
        "modified": [],
        "unchanged": [],
    }

    all_keys = set(old_plan.keys()) | set(new_plan.keys())

    for key in all_keys:
        in_old = key in old_plan
        in_new = key in new_plan

        if in_old and not in_new:
            result["removed"].append({"key": key, "value": old_plan[key]})
        elif not in_old and in_new:
            result["added"].append({"key": key, "value": new_plan[key]})
        elif old_plan[key] == new_plan[key]:
            result["unchanged"].append({"key": key, "value": old_plan[key]})
        else:
            result["modified"].append({
                "key": key,
                "old": old_plan[key],
                "new": new_plan[key],
            })

    return result


def format_diff_report(diff: dict[str, Any]) -> str:
    """将差异报告格式化为可读文本。

    Args:
        diff: compare_plans 返回的差异报告

    Returns:
        格式化的文本
    """
    lines = []

    if diff["added"]:
        lines.append("【新增内容】")
        for item in diff["added"]:
            lines.append(f"  + {item['key']}: {_summarize_value(item['value'])}")

    if diff["removed"]:
        lines.append("【删除内容】")
        for item in diff["removed"]:
            lines.append(f"  - {item['key']}: {_summarize_value(item['value'])}")

    if diff["modified"]:
        lines.append("【修改内容】")
        for item in diff["modified"]:
            lines.append(f"  ~ {item['key']}:")
            lines.append(f"      旧: {_summarize_value(item['old'])}")
            lines.append(f"      新: {_summarize_value(item['new'])}")

    if diff["unchanged"]:
        lines.append(f"【未变内容】共 {len(diff['unchanged'])} 项")

    if not any([diff["added"], diff["removed"], diff["modified"]]):
        lines = ["新旧计划完全相同，无差异。"]

    return "\n".join(lines)


def _summarize_value(value: Any, max_len: int = 100) -> str:
    """将值转为简洁的文本摘要。"""
    text = str(value)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text
