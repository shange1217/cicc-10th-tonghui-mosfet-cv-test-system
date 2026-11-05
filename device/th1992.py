# device/th1992.py
"""
TH1992 双通道源表。

按分赛区决赛《控制逻辑》与技术文档（CICC 团队）：
- CH1 = DC_H = MOSFET 漏极电压（0~100 V）
- CH2 = +5 V = PCB / 继电器板供电
栅极偏置由 LCR 内部直流偏置源（BIAS:VOLT）提供，不接 TH1992。

电源管理约定：
- 一次测试会话开始时 pcb_on()，整个会话保持 5 V；
- 每个测量阶段只调 output_drain()/drain_off()，不反复开关 5 V；
- 只有复位/关窗/急停才 output_off() 全关。
"""
from PyQt5.QtCore import QThread

from .serial_device import SerialDevice
from core.scpi import TH1992_SCPI


class TH1992(SerialDevice):

    # 手册 V1.0.6 表 5-3：结束符 NL(0x0A)，不是 CRLF
    TERMINATOR = "\n"

    def __init__(self):
        super().__init__("TH1992")
        self._pcb_on = False

    def init_device(self) -> bool:
        try:
            self.send_scpi(TH1992_SCPI.RESET)
            self.send_scpi(TH1992_SCPI.CH1_OFF)
            self.send_scpi(TH1992_SCPI.CH2_OFF)
            self._pcb_on = False
            return True
        except Exception:
            return False

    # -- 校验 -------------------------------------------------------------
    @staticmethod
    def _check_drain(drain_v: float) -> float:
        v = float(drain_v)
        if not (0.0 <= v <= 100.0):
            raise ValueError(f"漏极电压 {v} V 超出 0~100 V")
        return v

    @staticmethod
    def _check_pcb(pcb_v: float) -> float:
        v = float(pcb_v)
        if not (4.5 <= v <= 5.5):
            raise ValueError(f"PCB 供电 {v} V 超出 4.5~5.5 V")
        return v

    # -- 会话级电源 -------------------------------------------------------
    def pcb_on(self, pcb_v: float = 5.0) -> None:
        """打开 CH2 +5 V 板供电；重复调用不会重复下发。"""
        if self._pcb_on:
            return
        v = self._check_pcb(pcb_v)
        self.send_scpi(TH1992_SCPI.ch2_voltage(v))
        QThread.msleep(20)
        self.send_scpi(TH1992_SCPI.CH2_ON)
        self._pcb_on = True

    def pcb_off(self) -> None:
        # 先回 0V 再断开，符合控制逻辑“电压变成0，再断开”
        self.send_scpi(TH1992_SCPI.ch2_voltage(0.0))
        self.send_scpi(TH1992_SCPI.CH2_OFF)
        self._pcb_on = False

    # -- 漏极 -------------------------------------------------------------
    def output_drain(self, drain_v: float) -> None:
        """设置并打开 CH1 漏极电压；不动 CH2。"""
        v = self._check_drain(drain_v)
        self.send_scpi(TH1992_SCPI.ch1_voltage(v))
        QThread.msleep(20)
        self.send_scpi(TH1992_SCPI.CH1_ON)

    def drain_off(self) -> None:
        # 先回 0V 再断开
        self.send_scpi(TH1992_SCPI.ch1_voltage(0.0))
        self.send_scpi(TH1992_SCPI.CH1_OFF)

    # -- 兼容接口 ---------------------------------------------------------
    def output_on(self, drain_v: float, pcb_v: float = 5.0) -> None:
        """先开 5 V 板供电，再开漏极；参数顺序固定为 (drain, pcb)。"""
        self.pcb_on(pcb_v)
        self.output_drain(drain_v)

    def output_off(self) -> None:
        """急停/关窗：先关漏极，再关 5 V。"""
        try:
            self.drain_off()
        finally:
            self.pcb_off()
