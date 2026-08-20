"""SOP 执行器——读取 YAML 配置，按步骤执行差距分析。

工作流程：
1. 加载 SOP 配置（YAML）
2. 按步骤依次执行
3. 每步调用 LLM 分析（返回 prompt，由 MCP 客户端执行）
4. 收集中间输出，传递给下一步
5. 返回完整分析报告 + 中间过程
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .data_source import DataRouter

# SOP 配置文件目录
SOP_DIR = Path(__file__).parent.parent.parent / "sop"


def load_sop(name: str) -> dict[str, Any]:
    """加载 SOP 配置。

    Args:
        name: SOP 名称（对应 sop/ 目录下的 YAML 文件名，不含扩展名）

    Returns:
        解析后的 SOP 配置 dict

    Raises:
        FileNotFoundError: 配置文件不存在
    """
    sop_file = SOP_DIR / f"{name}.yaml"
    if not sop_file.exists():
        raise FileNotFoundError(f"SOP 配置文件不存在：{sop_file}")

    with open(sop_file, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_step_prompt(
    step: dict[str, Any],
    context: dict[str, Any],
) -> str:
    """构建单步的 LLM prompt。

    Args:
        step: SOP 步骤配置
        context: 上下文变量（之前步骤的输出 + 用户档案数据）

    Returns:
        格式化后的 prompt 字符串
    """
    template = step.get("prompt_template", "")
    if not template:
        return ""

    # 安全格式化：只替换模板中存在的变量，忽略缺失的
    try:
        return template.format(**context)
    except KeyError:
        # 如果有缺失变量，尝试用 {key} 保留原文
        result = template
        for key, value in context.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result


def execute_sop(
    sop_name: str,
    user_have: dict[str, Any],
    user_want: dict[str, Any],
    target_jd: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """执行 SOP，返回分步结果。

    注意：这个函数不直接调用 LLM，而是构建每步需要的 prompt 和上下文。
    实际的 LLM 调用由 MCP 客户端（Claude）完成。

    Args:
        sop_name: SOP 名称（resume_screening / interview_prep）
        user_have: 用户现状
        user_want: 用户目标
        target_jd: 目标 JD（可选）

    Returns:
        {
            "sop_name": str,
            "steps": [
                {
                    "id": str,
                    "name": str,
                    "description": str,
                    "prompt": str,           # 需要发给 LLM 的 prompt
                    "data_source_query": str, # 数据源查询（如有）
                    "local_search_paths": list[str],  # 本地搜索路径（如有）
                    "output_fields": list[str],
                }
            ],
            "context": dict,  # 初始上下文
        }
    """
    sop_config = load_sop(sop_name)
    router = DataRouter()

    # 构建初始上下文
    context = {
        "user_have": json.dumps(user_have, ensure_ascii=False, indent=2) if user_have else "（未填写）",
        "user_want": json.dumps(user_want, ensure_ascii=False, indent=2) if user_want else "（未填写）",
    }
    if target_jd:
        context["target_jd"] = json.dumps(target_jd, ensure_ascii=False, indent=2)

    steps_output = []

    for step in sop_config.get("steps", []):
        step_info = {
            "id": step["id"],
            "name": step["name"],
            "description": step.get("description", ""),
            "output_fields": step.get("output_fields", []),
        }

        # 如果有数据源查询，先检索
        if step.get("data_source"):
            query_template = step.get("query_template", "")
            search_paths = step.get("local_search_paths")

            # 安全格式化：跳过引用了未生成变量的模板
            try:
                query = query_template.format(**context) if query_template else ""
            except KeyError:
                # 模板引用了还未生成的变量（如 persona.xxx），跳过此步的查询
                query = ""
                step_info["skipped_reason"] = "依赖前序步骤输出，将在完整流程中执行"

            # 检索数据
            if query:
                search_result = router.search(query, step["data_source"], search_paths)
                step_info["data_source_query"] = query
                step_info["local_search_paths"] = search_paths or []
                step_info["search_results"] = search_result.get("results", [])
                step_info["has_local_data"] = search_result.get("has_local", False)
                # 将检索结果注入上下文，供后续 prompt 使用
                if search_result.get("results"):
                    context[f"{step['id']}_data"] = "\n".join(
                        r.get("content", "")[:500] for r in search_result["results"][:3]
                    )
            else:
                step_info["data_source_query"] = ""
                step_info["local_search_paths"] = search_paths or []
                step_info["skipped_reason"] = step_info.get("skipped_reason", "查询为空")

        # 构建 prompt
        if step.get("prompt_template"):
            step_info["prompt"] = build_step_prompt(step, context)

        steps_output.append(step_info)

    return {
        "sop_name": sop_config.get("name", sop_name),
        "sop_version": sop_config.get("version", "1.0"),
        "description": sop_config.get("description", ""),
        "steps": steps_output,
        "context": context,
    }


def execute_sop_with_retrieval(
    sop_name: str,
    user_have: dict[str, Any],
    user_want: dict[str, Any],
    target_jd: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """执行 SOP，包含实际数据检索。

    和 execute_sop 的区别：这个函数会真正调用 DataRouter 检索数据。

    Args:
        sop_name: SOP 名称
        user_have: 用户现状
        user_want: 用户目标
        target_jd: 目标 JD（可选）

    Returns:
        包含检索结果的 SOP 执行结果
    """
    sop_config = load_sop(sop_name)
    router = DataRouter()

    context = {
        "user_have": json.dumps(user_have, ensure_ascii=False, indent=2) if user_have else "（未填写）",
        "user_want": json.dumps(user_want, ensure_ascii=False, indent=2) if user_want else "（未填写）",
    }
    if target_jd:
        context["target_jd"] = json.dumps(target_jd, ensure_ascii=False, indent=2)

    steps_output = []

    for step in sop_config.get("steps", []):
        step_info = {
            "id": step["id"],
            "name": step["name"],
            "description": step.get("description", ""),
            "output_fields": step.get("output_fields", []),
        }

        # 数据源检索
        if step.get("data_source"):
            query_template = step.get("query_template", "")
            query = ""
            try:
                query = query_template.format(**context) if query_template else ""
            except KeyError:
                # 模板引用了还未生成的变量，用原始模板作为查询
                query = query_template

            search_paths = step.get("local_search_paths")
            search_result = router.search(query, step["data_source"], search_paths)

            step_info["data_source_query"] = query
            step_info["local_search_paths"] = search_paths or []
            step_info["search_results"] = search_result.get("results", [])
            step_info["has_local_data"] = search_result.get("has_local", False)
            step_info["fallback_to_llm"] = search_result.get("fallback_to_llm", True)

            # 将检索结果加入上下文，供后续步骤使用
            if search_result.get("results"):
                results_text = "\n\n".join(
                    f"[来源: {r['source']}]\n{r['content']}"
                    for r in search_result["results"]
                    if r.get("content")
                )
                for field in step.get("output_fields", []):
                    context[field] = results_text if results_text else "（未找到相关数据，请基于你的行业知识分析）"
            else:
                for field in step.get("output_fields", []):
                    context[field] = "（未找到相关数据，请基于你的行业知识分析）"

        # 构建 prompt
        if step.get("prompt_template"):
            step_info["prompt"] = build_step_prompt(step, context)

        steps_output.append(step_info)

    return {
        "sop_name": sop_config.get("name", sop_name),
        "sop_version": sop_config.get("version", "1.0"),
        "description": sop_config.get("description", ""),
        "steps": steps_output,
        "context": context,
    }
