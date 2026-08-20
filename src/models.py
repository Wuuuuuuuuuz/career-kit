"""数据模型——职业档案的核心结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """递归合并字典，update 中的值覆盖 base，嵌套字典做深度合并而非替换。"""
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


class PlanVersion(BaseModel):
    """计划版本快照。"""
    version: int
    timestamp: str
    content: dict[str, Any]
    source: str  # "generated" | "imported" | "manual"
    import_file: str | None = None


class CareerProfile(BaseModel):
    """职业档案。只强制 5 个 section，内部放什么由 LLM 根据用户情况决定。"""

    who: dict[str, Any] = Field(default_factory=dict, description="你是谁")
    have: dict[str, Any] = Field(default_factory=dict, description="你有什么")
    want: dict[str, Any] = Field(default_factory=dict, description="你想要什么")
    gap: dict[str, Any] = Field(default_factory=dict, description="差距是什么")
    plan: dict[str, Any] = Field(default_factory=dict, description="怎么走")

    # TODO: 后续扩展 - 支持多个目标 JD 对比
    target_jd: dict[str, Any] = Field(default_factory=dict, description="目标岗位 JD 解析结果")

    plan_history: list[PlanVersion] = Field(default_factory=list, description="计划版本历史")

    summary: str = ""
    version: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def touch(self) -> None:
        """更新版本号和时间戳。"""
        self.version += 1
        self.updated_at = datetime.now().isoformat()

    def merge(self, section: str, data: dict[str, Any]) -> None:
        """将 data 深度合并到指定 section，然后更新版本和时间戳。"""
        if section not in ("who", "have", "want", "gap", "plan"):
            raise ValueError(f"未知 section：{section}，必须是 who/have/want/gap/plan")
        target = getattr(self, section)
        _deep_merge(target, data)
        self.touch()

    def save_plan_snapshot(self, source: str, import_file: str | None = None) -> None:
        """保存当前 plan 到版本历史。"""
        snapshot = PlanVersion(
            version=len(self.plan_history) + 1,
            timestamp=datetime.now().isoformat(),
            content=self.plan.copy(),
            source=source,
            import_file=import_file,
        )
        self.plan_history.append(snapshot)

    def restore_plan_version(self, version: int) -> None:
        """恢复到指定版本的计划。"""
        for snapshot in self.plan_history:
            if snapshot.version == version:
                self.plan = snapshot.content.copy()
                self.touch()
                return
        raise ValueError(f"版本 {version} 不存在")
