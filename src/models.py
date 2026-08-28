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


class TaskStatus(str):
    """任务状态。"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class Task(BaseModel):
    """任务模型。产品不规划时间：任务只有顺序和状态，快慢由用户掌握。

    打卡点（BUG-004）：checkin_mode 由详细路线 LLM 设计——
    - once: 一次性完成（默认）
    - daily: 按天打卡（checkin_goal = 需要打卡的天数）
    - percent: 按比例打卡（checkin_goal = 目标比例，如 80）
    checkin_progress 记录当前进度（daily 累加天数 / percent 累加比例）。
    """
    id: str
    name: str
    description: str = ""
    phase_id: str = ""
    milestone_id: str = ""
    status: str = TaskStatus.PENDING
    priority: str = "medium"  # high | medium | low
    started_at: str | None = None
    completed_at: str | None = None
    checkin_mode: str = ""  # once | daily | percent（空 = once）
    checkin_goal: float = 0  # daily: 目标天数；percent: 目标比例（如 80 表示 80%）
    checkin_progress: float = 0  # 当前累计（daily: 已打卡天数；percent: 已完成比例）

    def start(self) -> None:
        """开始任务。"""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now().isoformat()

    def complete(self) -> None:
        """完成任务。"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()

    def skip(self, reason: str = "") -> None:
        """跳过任务。"""
        self.status = TaskStatus.SKIPPED
        self.completed_at = datetime.now().isoformat()
        if reason:
            self.description = f"{self.description} [跳过原因: {reason}]".strip()


class CheckIn(BaseModel):
    """打卡记录。"""
    task_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    status: str = TaskStatus.COMPLETED
    notes: str = ""
    amount: float = 0  # 本次打卡量（daily: 1 天；percent: 本次完成比例）


class Adjustment(BaseModel):
    """调整记录。"""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    trigger: str = ""
    trigger_type: str = ""  # stage_audit | event（proactive 已随时间概念退场移除）
    reason: str = ""
    changes: list[dict[str, Any]] = Field(default_factory=list)
    approved: bool = True


class PlanVersion(BaseModel):
    """计划版本快照。"""
    version: int
    timestamp: str
    content: dict[str, Any]
    source: str  # "generated" | "imported" | "manual"
    import_file: str | None = None


class JourneyEntry(BaseModel):
    """学习轨迹条目——记录每次交互的知识和产出。"""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    phase: str = ""  # "analysis" | "learning" | "interview" | "adjustment"
    knowledge: list[dict[str, Any]] = Field(default_factory=list)  # 搜索结果、参考资料
    analysis: dict[str, Any] = Field(default_factory=dict)  # 中间分析产出
    decision: str = ""  # 用户做了什么决定
    plan_changes: dict[str, Any] = Field(default_factory=dict)  # 计划调整


class CareerProfile(BaseModel):
    """职业档案。只强制 5 个 section，内部放什么由 LLM 根据用户情况决定。"""

    who: dict[str, Any] = Field(default_factory=dict, description="你是谁")
    have: dict[str, Any] = Field(default_factory=dict, description="你有什么")
    want: dict[str, Any] = Field(default_factory=dict, description="你想要什么")
    gap: dict[str, Any] = Field(default_factory=dict, description="差距是什么")
    plan: dict[str, Any] = Field(default_factory=dict, description="怎么走")

    # TODO: 后续扩展 - 支持多个目标 JD 对比
    target_jd: dict[str, Any] = Field(default_factory=dict, description="目标岗位 JD 解析结果")

    # Phase 2: 任务管理
    tasks: list[Task] = Field(default_factory=list, description="任务列表")
    checkins: list[CheckIn] = Field(default_factory=list, description="打卡记录")
    adjustments: list[Adjustment] = Field(default_factory=list, description="调整历史")

    plan_history: list[PlanVersion] = Field(default_factory=list, description="计划版本历史")
    journey: list[JourneyEntry] = Field(default_factory=list, description="学习轨迹——记录每次交互的知识和产出")

    # 阶段审计记录：已触发过阶段审计的 phase_id 不再重复触发
    audited_phases: list[str] = Field(default_factory=list, description="已完成审计的阶段 id 列表")

    # 目标变更检测依据：各 section 最近更新时间 / 路线图保存时间
    section_updated_at: dict[str, str] = Field(default_factory=dict, description="各 section 最近一次写入时间")
    plan_saved_at: str = ""  # save_roadmap 每次覆盖

    # 摸排门禁（BUG-001 硬性要求）：have 有技能但无用户确认证据时 finalize 不放行，
    # 唯一跳过方式是用户明确提出（finalize_profile(skip_probing=True)），标记留痕
    probe_skipped: bool = False

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
        self.section_updated_at[section] = datetime.now().isoformat()
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

    def append_journey(self, entry: JourneyEntry) -> None:
        """追加学习轨迹条目并更新版本。"""
        self.journey.append(entry)
        self.touch()

    def get_task(self, task_id: str) -> Task | None:
        """获取指定 ID 的任务。"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def add_task(self, task: Task) -> None:
        """添加任务。"""
        self.tasks.append(task)
        self.touch()

    def add_checkin(self, checkin: CheckIn) -> None:
        """添加打卡记录。"""
        self.checkins.append(checkin)
        self.touch()

    def add_adjustment(self, adjustment: Adjustment) -> None:
        """添加调整记录。"""
        self.adjustments.append(adjustment)
        self.touch()
