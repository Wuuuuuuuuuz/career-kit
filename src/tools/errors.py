"""统一错误处理模块。

所有 MCP tool 的错误都通过本模块抛出和格式化，
确保返回给 LLM 的错误格式一致、语义清晰。
"""

from __future__ import annotations

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


def error_response(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """返回标准错误格式。"""
    return {
        "isError": True,
        "code": code,
        "message": message,
        "details": details or {},
    }


def exception_to_response(exc: CareerKitError) -> dict[str, Any]:
    """将 CareerKitError 异常转为标准错误响应。"""
    return error_response(exc.code, exc.message, exc.details)


def raise_or_return(result: Any) -> Any:
    """如果 result 是 CareerKitError 实例，转为标准 dict 返回；否则原样返回。"""
    if isinstance(result, CareerKitError):
        return exception_to_response(result)
    return result
