# core/measurement.py
"""测量条件与重复性统计。

目的：记录每条结果的测量条件、采样点数与离散度。CSV 字段与 `MeasurementResult.to_row()` 一一对应。

单位约定：电容 pF、电阻/阻抗 Ω、频率 Hz、电压 V。
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from statistics import median, pstdev
from typing import Iterable, Sequence


@dataclass(frozen=True)
class MeasurementSpec:
    """一次测量的完整条件。"""

    name: str
    lcr_function: str      # CPD / ZTD / RXD ...
    freq_hz: float
    ac_level_v: float
    gate_v: float
    drain_v: float
    relay_state: str       # CISS / COSS / CRSS / RGOPEN / RGSHORT / OPEN ...
    note: str = ""

    def condition_text(self) -> str:
        return (f"{self.lcr_function} @ {self.freq_hz / 1e6:.3f} MHz, "
                f"AC {self.ac_level_v * 1e3:.0f} mV, "
                f"Vg(LCR bias)={self.gate_v:.1f} V, "
                f"Vd(TH1992 CH1)={self.drain_v:.1f} V, PCB=5.0 V, "
                f"继电器={self.relay_state}")


@dataclass
class MeasurementResult:
    spec: MeasurementSpec
    unit: str
    values: list[float]
    timestamp: str
    median: float
    mean: float
    std: float
    minimum: float
    maximum: float
    n: int
    spread_pct: float
    secondary_median: float | None = None
    secondary_unit: str = ""
    secondary_values: list[float] = field(default_factory=list)

    def condition_text(self) -> str:
        return self.spec.condition_text()

    def to_row(self) -> list[str]:
        s = self.spec
        return [
            self.timestamp, s.name, self.unit,
            "" if self.secondary_median is None else f"{self.secondary_median:.6g}",
            self.secondary_unit,
            str(self.n),
            f"{self.median:.6g}", f"{self.mean:.6g}", f"{self.std:.6g}",
            f"{self.minimum:.6g}", f"{self.maximum:.6g}", f"{self.spread_pct:.2f}",
            f"{s.freq_hz:.0f}", f"{s.ac_level_v:.3f}",
            f"{s.gate_v:.1f}", f"{s.drain_v:.1f}",
            s.relay_state, s.lcr_function,
            ";".join(f"{v:.6g}" for v in self.values),
        ]


CSV_HEADER: list[str] = [
    "timestamp", "param", "unit", "secondary_median", "secondary_unit", "n",
    "median", "mean", "std", "min", "max", "spread_pct",
    "freq_hz", "ac_level_v", "gate_v", "drain_v", "relay", "function", "raw_values",
]


def summarize(spec: MeasurementSpec,
              values: Iterable[float],
              unit: str,
              *,
              secondary_values: Iterable[float] | None = None,
              secondary_unit: str = "",
              timestamp: str | None = None,
              min_points: int = 3) -> MeasurementResult:
    """把原始采样汇总成结果；有效点不足时抛 ValueError，避免把噪声当数据。"""
    vals = [float(v) for v in values]
    if len(vals) < min_points:
        raise ValueError(f"{spec.name}: 有效点数 {len(vals)} < {min_points}，拒绝出结果")
    sec_vals = [float(v) for v in (secondary_values or [])]
    med = median(vals)
    mean = sum(vals) / len(vals)
    std = pstdev(vals) if len(vals) > 1 else 0.0
    lo, hi = min(vals), max(vals)
    spread = (hi - lo) / abs(med) * 100.0 if med else 0.0
    return MeasurementResult(
        spec=spec,
        unit=unit,
        values=vals,
        timestamp=timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        median=med,
        mean=mean,
        std=std,
        minimum=lo,
        maximum=hi,
        n=len(vals),
        spread_pct=spread,
        secondary_median=median(sec_vals) if sec_vals else None,
        secondary_unit=secondary_unit,
        secondary_values=sec_vals,
    )


def rg_consistency_warning(open_result: MeasurementResult,
                           short_result: MeasurementResult,
                           tolerance_pct: float = 2.0) -> str:
    """Rg(开) 与 Rg(短) 应明显不同；几乎相同说明短路态没真正短接。"""
    a = abs(open_result.median)
    b = abs(short_result.median)
    base = max(a, b, 1e-12)
    diff = abs(a - b) / base * 100.0
    if diff < tolerance_pct:
        return (f"Rg(开)={a:.4g} Ω 与 Rg(短)={b:.4g} Ω 仅差 {diff:.2f}%，"
                f"短路态可能未真正短接，请检查继电器/夹具")
    return ""


def repeatability_warnings(result: MeasurementResult,
                           spread_limit_pct: float = 10.0,
                           min_points: int = 5) -> list[str]:
    """返回需要写进日志的重复性告警。"""
    out: list[str] = []
    if result.n < min_points:
        out.append(f"{result.spec.name}: 有效点仅 {result.n} 个，重复性不足")
    if result.spread_pct > spread_limit_pct:
        out.append(f"{result.spec.name}: 极差 {result.spread_pct:.1f}% "
                   f"超过 {spread_limit_pct:.0f}% 阈值，建议检查夹具/接触")
    return out


def write_results_csv(path: str, results: Sequence[MeasurementResult]) -> None:
    """写汇总 CSV：一行一次测量，原始点用分号放在最后一列。"""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        for r in results:
            writer.writerow(r.to_row())
