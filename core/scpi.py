# core/scpi.py
"""
TH2840E/TH2840 LCR 仪表 SCPI 命令集 + TH1992 源表命令
按用户手册 V1.0.6 定义 (Tonghui 同惠通用)
"""
from dataclasses import dataclass


@dataclass
class CMD:
    cmd: str
    desc: str = ""
    timeout_ms: int = 800


class TH2840_SCPI:
    """TH2840E 精密 LCR 表 SCPI 命令"""

    # -- 系统 ----------------------------------------
    RST = CMD("*RST", "复位", 5000)
    CLS = CMD("*CLS", "清除状态")
    IDN = CMD("*IDN?", "查询身份")
    OPC = CMD("*OPC?", "等待完成", 5000)

    # -- 测量页面 ------------------------------------
    DISP_MEAS = CMD("DISP:PAGE MEAS", "测量显示页")

    # -- 测量功能（TH2840 手册 7.2.11：:FUNC:IMP para1,para2）----------
    FUNC_PAIRS = {
        "CP,D": "CP,D", "CP,Q": "CP,Q", "CP,GP": "CP,GP", "CP,RP": "CP,RP",
        "CS,RS": "CS,RS", "CS,D": "CS,D", "CS,Q": "CS,Q",
        "LP,RP": "LP,RP", "LP,Q": "LP,Q",
        "LS,RS": "LS,RS", "LS,Q": "LS,Q",
        "RS,X": "RS,X", "Z,ZTD": "Z,ZTD",
    }

    @staticmethod
    def func_pair(pair: str) -> CMD:
        return CMD(f"FUNC:IMP {pair}", f"功能={pair}")

    @staticmethod
    def func_cpd() -> CMD:
        return TH2840_SCPI.func_pair("CP,D")

    @staticmethod
    def func_ztd() -> CMD:
        return TH2840_SCPI.func_pair("Z,ZTD")

    @staticmethod
    def func_rxd() -> CMD:
        return TH2840_SCPI.func_pair("RS,X")

    FUNC_QUERY = CMD("FUNC:IMP?", "查询当前参数")

    # -- 频率 ----------------------------------------
    @staticmethod
    def freq(hz: float) -> CMD:
        return CMD(f"FREQ {hz:.0f}", f"频率={hz}Hz")

    # -- 电平 ----------------------------------------
    @staticmethod
    def voltage(v: float) -> CMD:
        return CMD(f"VOLT {v:.3f}", f"电平={v}V")

    # -- 偏置 ----------------------------------------
    @staticmethod
    def dc_bias(v: float) -> CMD:
        return CMD(f"BIAS:VOLT {v:.1f}", f"DC偏置={v}V")

    BIAS_ON  = CMD("BIAS:STAT ON", "DC偏置开")
    BIAS_OFF = CMD("BIAS:STAT OFF", "DC偏置关")

    # -- 量程 ----------------------------------------
    RANGE_AUTO = CMD("FUNC:IMP:RANG:AUTO ON", "自动量程")

    # -- 触发 ----------------------------------------
    TRIG_CONT = CMD("TRIG:SOUR CONT", "连续触发")
    TRIG_SING = CMD("TRIG:SOUR SING", "单次触发")
    TRIG_ONE  = CMD("TRIG", "执行一次触发", 1000)

    # -- 速度 ----------------------------------------
    SPEED_FAST   = CMD("APER FAST", "快速")
    SPEED_MEDIUM = CMD("APER MED", "中速")
    SPEED_SLOW   = CMD("APER SLOW", "慢速")

    @staticmethod
    def average(speed: str, n: int) -> CMD:
        return CMD(f"APER {speed},{int(n)}", f"平均次数={int(n)}")

    # -- 量程 ----------------------------------------
    @staticmethod
    def range_value(n: float) -> CMD:
        return CMD(f"FUNC:IMP:RANG {float(n):.0f}", f"AC量程={n}")

    # -- 校准 (全频) ---------------------------------
    CORR_CLEAR   = CMD("CORR:CLE", "清除全部校正", 2000)
    CORR_OPEN    = CMD("CORR:OPEN", "全频开路校准", 30000)
    CORR_SHORT   = CMD("CORR:SHOR", "全频短路校准", 30000)
    CORR_OPEN_EN = CMD("CORR:OPEN:STAT ON", "启用开路补偿")
    CORR_SHORT_EN = CMD("CORR:SHOR:STAT ON", "启用短路补偿")
    CORR_OPEN_Q  = CMD("CORR:OPEN:STAT?", "查询开路补偿")
    CORR_SHORT_Q = CMD("CORR:SHOR:STAT?", "查询短路补偿")

    # -- 读取 ----------------------------------------
    FETCH = CMD("FETC?", "读取4参数", 500)

    # -- 列表扫描 ------------------------------------
    @staticmethod
    def list_total(n: int) -> CMD:
        return CMD(f"LIST:TOTAL {n}", f"列表总点数={n}")

    @staticmethod
    def list_freq(values: str) -> CMD:
        return CMD(f"LIST:FREQ {values}", "列表频率")

    @staticmethod
    def list_volt(values: str) -> CMD:
        return CMD(f"LIST:VOLT {values}", "列表电平")

    @staticmethod
    def list_sweep_freq(start_hz: float, stop_hz: float, points: int) -> list[CMD]:
        """生成等间隔频率扫描命令序列（LIST:TOTAL / LIST:FREQ / LIST:MODE）。

        TH2840 手册 7.2.13：LIST:MODE 取 SEQ/STEP；TRIG:SOUR 只有 CONT/SING，
        原实现发 `TRIG:SOUR SEQ` 是非法值。
        """
        n = max(2, min(201, int(points)))
        if start_hz <= 0 or stop_hz <= start_hz:
            raise ValueError(f"非法扫描区间: {start_hz} -> {stop_hz}")
        step = (stop_hz - start_hz) / (n - 1)
        values = ",".join(f"{start_hz + i * step:.0f}" for i in range(n))
        return [
            TH2840_SCPI.list_total(n),
            TH2840_SCPI.list_freq(values),
            TH2840_SCPI.LIST_MODE_SEQ,
        ]

    LIST_MODE_SEQ  = CMD("LIST:MODE SEQ", "列表顺序扫描")
    LIST_FETCH     = CMD("FETC:LIST?", "读取列表数据", 3000)


class TH1992_SCPI:
    """TH1992 双通道源表 SCPI 命令 (CH1=Drain/DC_H, CH2=+5V PCB)

    手册 V1.0.6：命令结束符为 NL(0x0A)；输出开关为 :OUTPut[c]:STATe。
    """

    RESET   = CMD("*RST", "复位")
    CH1_ON  = CMD("OUTP1:STAT ON", "CH1输出开")
    CH1_OFF = CMD("OUTP1:STAT OFF", "CH1输出关")
    CH2_ON  = CMD("OUTP2:STAT ON", "CH2输出开")
    CH2_OFF = CMD("OUTP2:STAT OFF", "CH2输出关")

    @staticmethod
    def ch1_voltage(v: float) -> CMD:
        return CMD(f"SOUR1:VOLT {v:.3f}", f"CH1(漏极 DC_H)={v}V")

    @staticmethod
    def ch2_voltage(v: float) -> CMD:
        return CMD(f"SOUR2:VOLT {v:.3f}", f"CH2(PCB +5V)={v}V")
