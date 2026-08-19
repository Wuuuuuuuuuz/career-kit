"""数据模型——职业档案的核心结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CareerProfile(BaseModel):
    """职业档案。只强制 5 个 section，内部放什么由 LLM 根据用户情况决定。"""

    who: dict[str, Any] = Field(default_factory=dict, description="你是谁")
    have: dict[str, Any] = Field(default_factory=dict, description="你有什么")
    want: dict[str, Any] = Field(default_factory=dict, description="你想要什么")
    gap: dict[str, Any] = Field(default_factory=dict, description="差距是什么")
    plan: dict[str, Any] = Field(default_factory=dict, description="怎么走")

    summary: str = ""
    version: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def touch(self) -> None:
        """更新版本号和时间戳。"""
        self.version += 1
        self.updated_at = datetime.now().isoformat()
