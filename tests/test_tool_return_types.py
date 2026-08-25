"""MCP 工具返回类型防回归测试。

背景：FastMCP 根据返回类型注解生成 output schema。
工具声明 -> str 却返回 dict 会触发 schema 校验失败。

本测试用 AST 静态检查 server.py，确保：
1. 所有 @mcp.tool() 函数都声明 -> str
2. 函数体内没有裸的 return { 字面量（必须经过 _json() / json.dumps() 序列化）
3. error_response() 返回 str（运行时断言）
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

SERVER_PATH = Path(__file__).parent.parent / "src" / "server.py"


def _load_tool_functions():
    """解析 server.py，返回所有 @mcp.tool() 装饰函数的 AST 节点。"""
    tree = ast.parse(SERVER_PATH.read_text(encoding="utf-8"))
    tools = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            is_mcp_tool = (
                isinstance(deco, ast.Call)
                and isinstance(deco.func, ast.Attribute)
                and deco.func.attr == "tool"
            ) or (
                isinstance(deco, ast.Attribute)
                and deco.attr == "tool"
            )
            if is_mcp_tool:
                tools.append(node)
                break
    return tools


def test_all_tools_declare_str_return():
    """所有 MCP 工具必须声明 -> str。"""
    for fn in _load_tool_functions():
        returns = fn.returns
        assert returns is not None, f"工具 {fn.name} 缺少返回类型注解"
        annotation = ast.unparse(returns)
        assert annotation == "str", (
            f"工具 {fn.name} 返回类型是 {annotation}，必须是 str"
        )


def test_no_bare_dict_returns_in_tools():
    """工具函数体内不允许裸 return { ... }（dict 字面量直接返回）。"""
    for fn in _load_tool_functions():
        for node in ast.walk(fn):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                line = node.lineno
                raise AssertionError(
                    f"工具 {fn.name} 第 {line} 行裸返回 dict 字面量。"
                    f"请改为 return _json({{...}})，否则 FastMCP 校验失败。"
                )


def test_error_response_returns_str():
    """error_response 必须返回字符串。"""
    from src.tools.errors import error_response, exception_to_response, MissingDataError

    result = error_response("TEST_CODE", "测试消息", {"key": "value"})
    assert isinstance(result, str), f"error_response 返回了 {type(result).__name__}"

    # 确认可反序列化且结构完整
    parsed = json.loads(result)
    assert parsed["isError"] is True
    assert parsed["code"] == "TEST_CODE"
    assert parsed["message"] == "测试消息"

    result2 = exception_to_response(MissingDataError("缺少数据", {"missing": "gap"}))
    assert isinstance(result2, str)
    parsed2 = json.loads(result2)
    assert parsed2["code"] == "MISSING_DATA"
