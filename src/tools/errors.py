"""统一错误处理模块。

MCP tool 的错误统一通过 error_response 返回标准 JSON 字符串，
确保返回给 LLM 的错误格式一致、语义清晰。
JSON 参数解析失败时用 InvalidJsonError 异常在调用方内部传递。

注意：所有函数返回 JSON 字符串而非 dict。
MCP 工具的返回类型注解为 str，返回 dict 会触发 FastMCP schema 校验失败。
"""

from __future__ import annotations

import json
from typing import Any


class CareerKitError(Exception):
    """基础异常类。"""

    code: str = "UNKNOWN_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class InvalidJsonError(CareerKitError):
    """JSON 解析失败。"""

    code = "INVALID_JSON"


def error_response(code: str, message: str, details: dict[str, Any] | None = None) -> str:
    """返回标准错误格式（JSON 字符串）。"""
    return json.dumps(
        {
            "isError": True,
            "code": code,
            "message": message,
            "details": details or {},
        },
        ensure_ascii=False,
    )
