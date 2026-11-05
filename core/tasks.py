"""测试流程模型：任务列表 + 显式状态机。

把“第几步、还剩几步、能不能暂停/停止”从 UI 里的多个布尔量收敛到一个对象，
方便 UI、CLI、测试共用同一份流程定义。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TestState(Enum):
    __test__ = False  # 避免 pytest 把枚举当成测试类收集

    IDLE = "idle"
    PREFLIGHT = "preflight"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"
    DONE = "done"


@dataclass(frozen=True)
class TaskSpec:
    key: str
    title: str
    kind: str          # preflight / calibration / measurement
    param: str = ""    # measurement 参数名


# 8 步：自检 + 开路 + 短路 + 五个测量
TASKS: tuple[TaskSpec, ...] = (
    TaskSpec("preflight", "连接/自检", "preflight"),
    TaskSpec("open_cal", "开路校准", "calibration", "open"),
    TaskSpec("short_cal", "短路校准", "calibration", "short"),
    TaskSpec("Ciss", "测量 CISS", "measurement", "Ciss"),
    TaskSpec("Coss", "测量 COSS", "measurement", "Coss"),
    TaskSpec("Crss", "测量 CRSS", "measurement", "Crss"),
    TaskSpec("Rg", "测量 RG(开)", "measurement", "Rg"),
    TaskSpec("Rgs", "测量 RG(短)", "measurement", "Rgs"),
)

PARAMS: tuple[str, ...] = ("Ciss", "Coss", "Crss", "Rg", "Rgs")


class TaskProgress:
    """纯状态机，不依赖 Qt；UI 只读它来刷新标签/进度条/按钮。"""

    def __init__(self, tasks: tuple[TaskSpec, ...] = TASKS):
        self.tasks = tasks
        self.index = 0
        self.state = TestState.IDLE

    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def current(self) -> TaskSpec:
        return self.tasks[min(self.index, self.total - 1)]

    @property
    def fraction(self) -> float:
        if self.state is TestState.IDLE:
            return 0.0
        if self.state is TestState.DONE:
            return 1.0
        return (self.index + 1) / self.total

    @property
    def label(self) -> str:
        if self.state is TestState.IDLE:
            return f"0/{self.total} · 空闲"
        return f"{self.index + 1}/{self.total} · {self.current.title}"

    def reset(self) -> None:
        self.index = 0
        self.state = TestState.IDLE

    def begin(self, index: int = 0) -> None:
        self.index = max(0, min(index, self.total - 1))
        self.state = TestState.RUNNING

    def set_index(self, index: int) -> None:
        self.index = max(0, min(index, self.total - 1))

    def pause(self) -> None:
        if self.state is TestState.RUNNING:
            self.state = TestState.PAUSED

    def resume(self) -> None:
        if self.state is TestState.PAUSED:
            self.state = TestState.RUNNING

    def stop(self) -> None:
        self.state = TestState.STOPPING

    def fail(self) -> None:
        self.state = TestState.ERROR

    def finish(self) -> None:
        self.index = self.total - 1
        self.state = TestState.DONE
