"""STM32 连接看门狗。

背景线程周期性探测（STATUS 查询），连续失败后置位 lost 事件；
UI 线程用 QTimer 检查事件并执行断电，避免跨线程操作界面。
"""
from __future__ import annotations

import threading
import time
from typing import Callable


class ConnectionWatchdog:
    def __init__(self,
                 probe: Callable[[], bool],
                 on_lost: Callable[[], None] | None = None,
                 interval_s: float = 2.0,
                 failures: int = 3):
        self._probe = probe
        self._on_lost = on_lost
        self._interval_s = max(0.05, float(interval_s))
        self._failures = max(1, int(failures))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.lost = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop.clear()
        self.lost.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="stm32-watchdog")
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def _run(self) -> None:
        misses = 0
        while not self._stop.wait(self._interval_s):
            try:
                ok = bool(self._probe())
            except Exception:
                ok = False
            if ok:
                misses = 0
                continue
            misses += 1
            if misses >= self._failures:
                self.lost.set()
                if self._on_lost is not None:
                    try:
                        self._on_lost()
                    except Exception:
                        pass
                return
