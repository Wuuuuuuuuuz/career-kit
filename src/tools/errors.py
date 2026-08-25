"""统一错误处理模块。

所有 MCP tool 的错误都通过本模块抛出和格式化，
确保返回给 LLM 的错误格式一致、语义清晰。

注意：所有函数返回 JSON 字符串而非 dict。
MCP 工具的返回类型注解为 str，返回 dict 会触发 FastMCP schema 校验失败。
"""

from __future__ import annotations

import json
from typing import Any


# ---------------------------------------------------------------------------
# 异常类
# ---------------------------------------------------------------------------

class CareerKitError(Exception):
    """基础异常类。"""

    code: str = "UNKNOWN_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ProfileNotFoundError(CareerKitError):
    """档案不存在。"""

    code = "PROFILE_NOT_FOUND"


class InvalidSectionError(CareerKitError):
    """无效的 section。"""

    code = "INVALID_SECTION"


class MissingDataError(CareerKitError):
    """缺少必要数据。"""

    code = "MISSING_DATA"


class AnalysisError(CareerKitError):
    """分析失败。"""

    code = "ANALYSIS_FAILED"


class InvalidJsonError(CareerKitError):
    """JSON 解析失败。"""

    code = "INVALID_JSON"


# ---------------------------------------------------------------------------
# 错误码 → 异常类映射（方便从 code 反查）
# ---------------------------------------------------------------------------

_ERROR_REGISTRY: dict[str, type[CareerKitError]] = {
    cls.code: cls for cls in CareerKitError.__subclasses__()
}


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


def exception_to_response(exc: CareerKitError) -> str:
    """将 CareerKitError 异常转为标准错误响应（JSON 字符串）。"""
    return error_response(exc.code, exc.message, exc.details)
