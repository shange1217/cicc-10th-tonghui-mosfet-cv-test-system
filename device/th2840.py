# device/th2840.py
"""
TH2840 精密 LCR 表设备驱动
"""
import sys, os
_SYS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SYS_ROOT not in sys.path:
    sys.path.insert(0, _SYS_ROOT)

from typing import Optional

from PyQt5.QtCore import QThread

from .serial_device import SerialDevice
from core.scpi import TH2840_SCPI


class TH2840(SerialDevice):
    """TH2840 精密 LCR 测试仪"""

    # 可选的主副参数组合 (显示名 → (SCPI代码, 描述))
    # R-X 模式同时支持 Cs-Rs / Ls-Rs: R=Rs, 从 X 换算 Cs 或 Ls
    PARAM_PAIRS = {
        "Cp-D":  ("CP,D", "并联电容-损耗"),
        "Cp-Q":  ("CP,Q", "并联电容-品质因数"),
        "Cs-D":  ("CS,D", "串联电容-损耗"),
        "Cs-Q":  ("CS,Q", "串联电容-品质因数"),
        "Cs-Rs": ("CS,RS", "串联电容-串联电阻"),
        "Lp-D":  ("LP,D", "并联电感-损耗"),
        "Lp-Q":  ("LP,Q", "并联电感-品质因数"),
        "Ls-D":  ("LS,D", "串联电感-损耗"),
        "Ls-Q":  ("LS,Q", "串联电感-品质因数"),
        "Ls-Rs": ("LS,RS", "串联电感-串联电阻"),
        "Z-Q":   ("Z,Q", "阻抗-品质因数"),
        "Z-D":   ("Z,D", "阻抗-损耗"),
        "R-Q":   ("RS,Q", "电阻-品质因数"),
        "R-X":   ("RS,X", "电阻-电抗"),
    }

    def __init__(self):
        super().__init__("TH2840")
        self._current_func = "CP,D"  # 默认 Cp-D 模式
        self._speed = "FAST"

    # -- 初始化 -----------------------------------------------------------
    def init_device(self) -> bool:
        try:
            self.send_scpi(TH2840_SCPI.RST)
            self.query("*OPC?", timeout_ms=5000)
            self.send_scpi(TH2840_SCPI.CLS)
            self.send_scpi(TH2840_SCPI.DISP_MEAS)
            self.send_scpi(TH2840_SCPI.func_cpd())
            return True
        except Exception:
            return False

    # -- 身份与补偿状态 ---------------------------------------------------
    def identify(self) -> str:
        """读取 *IDN?，确认串口连的是 LCR 而不是别的设备。"""
        return self.query_scpi(TH2840_SCPI.IDN)

    def correction_status(self) -> tuple[str, str]:
        """返回 (开路补偿, 短路补偿) 的仪器状态字符串。"""
        return (self.query_scpi(TH2840_SCPI.CORR_OPEN_Q),
                self.query_scpi(TH2840_SCPI.CORR_SHORT_Q))

    # -- 校准 -------------------------------------------------------------
    def _save_settings(self) -> dict:
        """保存当前参数, 校准结束后恢复"""
        return {"func": self._current_func}

    def _restore_settings(self, saved: dict):
        """恢复校准前的设置"""
        self.send_cmd(f"FUNC:IMP {saved['func']}")
        self._current_func = saved['func']  # 同步 Python 状态

    def _measure_once(self) -> Optional[str]:
        self.send_scpi(TH2840_SCPI.TRIG_CONT)        # 确保连续触发
        self.send_scpi(TH2840_SCPI.TRIG_ONE)          # 单次触发
        self.query("*OPC?", timeout_ms=2000)           # 等完成
        return self.query_scpi(TH2840_SCPI.FETCH)

    def calibrate_open(self, stm32=None) -> str:
        """开路校准: CORR:CLE → STM32全断 → CORR:OPEN → *OPC? → STAT ON"""
        saved = self._save_settings()
        try:
            self.send_scpi(TH2840_SCPI.CORR_CLEAR)
            if stm32 is not None and stm32.is_open():
                stm32.all_off()
            QThread.msleep(20)

            self.send_scpi(TH2840_SCPI.func_ztd())
            self.send_scpi(TH2840_SCPI.TRIG_CONT)
            self.send_scpi(TH2840_SCPI.freq(1000000))
            self.send_scpi(TH2840_SCPI.voltage(1.0))
            self.send_scpi(TH2840_SCPI.BIAS_OFF)
            self.send_scpi(TH2840_SCPI.SPEED_MEDIUM)
            self.send_scpi(TH2840_SCPI.RANGE_AUTO)
            QThread.msleep(400)

            self.send_scpi(TH2840_SCPI.CORR_OPEN)
            self.query("*OPC?", timeout_ms=30000)

            self.send_scpi(TH2840_SCPI.CORR_OPEN_EN)
            stat = self.query_scpi(TH2840_SCPI.CORR_OPEN_Q)

            self.send_scpi(TH2840_SCPI.TRIG_ONE)
            self.query("*OPC?", timeout_ms=500)
            v = self.query_scpi(TH2840_SCPI.FETCH)
            if v:
                parts = v.split(",")
                z = abs(float(parts[0])) if parts else 0
                unit = "ohm"
                if z >= 1e6: z /= 1e6; unit = "Mohm"
                elif z >= 1e3: z /= 1e3; unit = "kohm"
                msg = f"校验 |Z| = {z:.2f} {unit} | STAT={stat}"
            else:
                msg = f"校验跳过 | STAT={stat}"
            return f"1:{msg}"
        except Exception as e:
            return f"FAIL:开路校准异常 {e}"
        finally:
            self._restore_settings(saved)

    def calibrate_short(self, stm32=None) -> str:
        """短路校准: STM32短接 → CORR:SHOR → *OPC? → STAT ON"""
        saved = self._save_settings()
        try:
            if stm32 is not None and stm32.is_open():
                stm32.short_on()
            QThread.msleep(20)

            self.send_scpi(TH2840_SCPI.func_rxd())
            self.send_scpi(TH2840_SCPI.TRIG_CONT)
            self.send_scpi(TH2840_SCPI.freq(1000000))
            self.send_scpi(TH2840_SCPI.voltage(1.0))
            self.send_scpi(TH2840_SCPI.BIAS_OFF)
            self.send_scpi(TH2840_SCPI.SPEED_MEDIUM)
            self.send_scpi(TH2840_SCPI.RANGE_AUTO)
            QThread.msleep(300)

            self.send_scpi(TH2840_SCPI.CORR_SHORT)
            self.query("*OPC?", timeout_ms=30000)

            self.send_scpi(TH2840_SCPI.CORR_SHORT_EN)
            stat = self.query_scpi(TH2840_SCPI.CORR_SHORT_Q)
            return f"1:采集完成 | STAT={stat}"
        except Exception as e:
            return f"FAIL:短路校准异常 {e}"
        finally:
            if stm32 is not None and stm32.is_open():
                stm32.all_off()
            self._restore_settings(saved)

    def calibrate_load(self) -> str:
        """负载校准未实现：TH2840 手册没有 CORR:LOAD 执行命令。

        保留方法名，避免界面/外部代码 import 失败；但直接抛错，绝不向仪器
        下发未定义命令。
        """
        raise NotImplementedError(
            "TH2840 手册未定义 CORR:LOAD 执行命令；负载校准待实机确认后再实现"
        )

    # -- 参数设置 ---------------------------------------------------------
    def set_function(self, pair_code: str):
        if pair_code not in TH2840_SCPI.FUNC_PAIRS:
            pair_code = "CP,D"
        self.send_scpi(TH2840_SCPI.func_pair(pair_code))
        self._current_func = pair_code

    def set_frequency(self, hz: float):
        self.send_scpi(TH2840_SCPI.freq(hz))

    def set_voltage(self, v: float):
        self.send_scpi(TH2840_SCPI.voltage(v))

    def set_dc_bias(self, v: float):
        """设置 LCR 内部直流偏置；本系统栅极由 LCR 内部 bias 驱动，通常传 0 关闭。"""
        self.send_scpi(TH2840_SCPI.dc_bias(v))
        self.send_scpi(TH2840_SCPI.BIAS_ON if abs(v) > 1e-9 else TH2840_SCPI.BIAS_OFF)

    def set_speed(self, speed: str):
        speed_map = {"FAST": TH2840_SCPI.SPEED_FAST,
                     "MEDIUM": TH2840_SCPI.SPEED_MEDIUM,
                     "SLOW": TH2840_SCPI.SPEED_SLOW}
        key = speed.upper() if isinstance(speed, str) else "FAST"
        self._speed = "MED" if key == "MEDIUM" else ("SLOW" if key == "SLOW" else "FAST")
        self.send_scpi(speed_map.get(key, TH2840_SCPI.SPEED_FAST))

    def set_average(self, n: int):
        """平均次数：TH2840 手册 7.2.5 语法 :APER <FAST+|FAST|MED|SLOW>[,int]。"""
        count = max(1, min(255, int(n)))
        self.send_scpi(TH2840_SCPI.average(self._speed, count))

    def set_trigger(self, src: str):
        trig_map = {"CONT": TH2840_SCPI.TRIG_CONT,
                    "SING": TH2840_SCPI.TRIG_SING}
        self.send_scpi(trig_map.get(src, TH2840_SCPI.TRIG_CONT))

    def set_range_auto(self):
        self.send_scpi(TH2840_SCPI.RANGE_AUTO)

    def set_range_value(self, n: int):
        """手动量程：TH2840 手册 7.2.11 语法 :FUNC:IMP:RANG <float>。"""
        self.send_scpi(TH2840_SCPI.range_value(n))

    def apply_all(self, freq_hz: float, volt_v: float, bias_v: float,
                  speed: str, avg: int, trig: str, range_str: str = "AUTO"):
        """下发参数；平均次数和手动量程按 TH2840 手册实现。"""
        self.set_frequency(freq_hz)
        self.set_voltage(volt_v)
        self.set_dc_bias(bias_v)
        self.set_speed(speed)
        if avg and int(avg) > 1:
            self.set_average(int(avg))
        self.set_trigger(trig)
        if str(range_str).upper() == "AUTO":
            self.set_range_auto()
        else:
            try:
                self.set_range_value(float(range_str))
            except (TypeError, ValueError):
                self.set_range_auto()

    # -- 测量 -------------------------------------------------------------
    def fetch(self) -> Optional[dict]:
        """读取主副参数, 返回 {"A":主值, "B":副值} 或 None"""
        try:
            raw = self.query_scpi(TH2840_SCPI.FETCH)
            if not raw:
                return None
            parts = raw.split(",")
            if len(parts) >= 2:
                return {"A": float(parts[0]), "B": float(parts[1])}
            return None
        except (ValueError, TypeError):
            return None

    def poll(self) -> Optional[dict]:
        """轮询：按 :FUNC:IMP 的主/副参数代码缩放，匹配仪器面板显示。"""
        raw = self.fetch()
        if raw is None:
            return None

        a_val, b_val = raw["A"], raw["B"]
        code = self._current_func or "CP,D"
        parts = [p.strip().upper() for p in code.split(",")]
        primary_code = parts[0] if parts else "CP"
        secondary_code = parts[1] if len(parts) > 1 else ""

        unit_a = ""
        if primary_code in ("CP", "CS"):
            a_val *= 1e12
            unit_a = "pF"
            primary = "Cp" if primary_code == "CP" else "Cs"
        elif primary_code in ("LP", "LS"):
            a_val *= 1e6
            unit_a = "uH"
            primary = "Lp" if primary_code == "LP" else "Ls"
        elif primary_code == "Z":
            a_val /= 1000.0
            unit_a = "kΩ"
            primary = "Z"
        elif primary_code == "RS":
            unit_a = "Ω"
            primary = "Rs"
        else:
            primary = primary_code

        if secondary_code == "X":
            unit_b = "Ω"
            secondary = "X"
        elif secondary_code in ("RS", "RP"):
            unit_b = "Ω"
            secondary = secondary_code
        elif secondary_code == "GP":
            unit_b = "S"
            secondary = "GP"
        elif secondary_code == "ZTD":
            unit_b = "°"
            secondary = "θ"
        elif secondary_code in ("D", "Q"):
            unit_b = ""
            secondary = secondary_code
        elif secondary_code:
            unit_b = ""
            secondary = secondary_code
        else:
            unit_b = ""
            secondary = ""

        return {
            "A": a_val, "B": b_val,
            "unit_a": unit_a, "unit_b": unit_b,
            "primary": primary, "secondary": secondary,
        }

    # -- 列表扫描 ---------------------------------------------------------
    def setup_list_sweep(self, start_hz: float, stop_hz: float, points: int):
        for cmd in TH2840_SCPI.list_sweep_freq(start_hz, stop_hz, points):
            self.send_scpi(cmd)

    def fetch_sweep_data(self) -> list[float]:
        """读取扫描数据（FETC:LIST? 是本命令集里已定义的列表读取命令）"""
        raw = self.query_scpi(TH2840_SCPI.LIST_FETCH)
        if not raw:
            return []
        return [float(x) for x in raw.split(",") if x.strip()]
