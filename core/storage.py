"""SQLite 测量记录：把每次测试的条件、统计和原始点落盘，便于追溯。

CSV 仍然保留（导出视图），但数据库才是主记录：
- 每次一键/单测/连续测试生成一个 run_id；
- 运行信息（操作员、器件、校准号、温湿度）来自环境变量，避免改 UI；
- 一条测量一行，字段与 MeasurementResult.to_row() 对齐。
"""
from __future__ import annotations

import csv
import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from core.measurement import CSV_HEADER, MeasurementResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    operator TEXT,
    device_sn TEXT,
    calibration_id TEXT,
    temperature_c REAL,
    humidity_pct REAL,
    note TEXT,
    status TEXT
);
CREATE TABLE IF NOT EXISTS measurements(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    param TEXT NOT NULL,
    unit TEXT,
    secondary_median REAL,
    secondary_unit TEXT,
    n INTEGER,
    median REAL,
    mean REAL,
    std REAL,
    min REAL,
    max REAL,
    spread_pct REAL,
    freq_hz REAL,
    ac_level_v REAL,
    gate_v REAL,
    drain_v REAL,
    relay TEXT,
    function TEXT,
    raw_values TEXT
);
CREATE INDEX IF NOT EXISTS idx_measurements_run ON measurements(run_id);
"""


def _env_float(name: str) -> float | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


@dataclass(frozen=True)
class RunMeta:
    operator: str = ""
    device_sn: str = ""
    calibration_id: str = ""
    temperature_c: float | None = None
    humidity_pct: float | None = None
    note: str = ""

    @classmethod
    def from_env(cls) -> "RunMeta":
        return cls(
            operator=os.getenv("MOS_OPERATOR") or os.getenv("USERNAME", ""),
            device_sn=os.getenv("MOS_DEVICE_SN", "TK9J90E"),
            calibration_id=os.getenv("MOS_CALIBRATION_ID", ""),
            temperature_c=_env_float("MOS_TEMPERATURE_C"),
            humidity_pct=_env_float("MOS_HUMIDITY_PCT"),
            note=os.getenv("MOS_NOTE", ""),
        )


class MeasurementStore:
    """极简 SQLite 存储；每次操作独立连接，避免跨线程共享连接。"""

    def __init__(self, path: str):
        self.path = path
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with self._db() as conn:
            conn.executescript(SCHEMA)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(measurements)")}
            if "secondary_median" not in cols:
                conn.execute("ALTER TABLE measurements ADD COLUMN secondary_median REAL")
            if "secondary_unit" not in cols:
                conn.execute("ALTER TABLE measurements ADD COLUMN secondary_unit TEXT")

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(self.path, timeout=5.0)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def start_run(self, meta: RunMeta, kind: str = "one_key") -> str:
        run_id = uuid.uuid4().hex
        with self._db() as conn:
            conn.execute(
                "INSERT INTO runs(id, kind, started_at, operator, device_sn, "
                "calibration_id, temperature_c, humidity_pct, note, status) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (run_id, kind, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 meta.operator, meta.device_sn, meta.calibration_id,
                 meta.temperature_c, meta.humidity_pct, meta.note, "running"),
            )
        return run_id

    def finish_run(self, run_id: str, status: str = "done") -> None:
        with self._db() as conn:
            conn.execute(
                "UPDATE runs SET finished_at=?, status=? WHERE id=?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status, run_id),
            )

    def add_result(self, run_id: str, result: MeasurementResult) -> None:
        s = result.spec
        with self._db() as conn:
            conn.execute(
                "INSERT INTO measurements(run_id, timestamp, param, unit, "
                "secondary_median, secondary_unit, n, median, "
                "mean, std, min, max, spread_pct, freq_hz, ac_level_v, gate_v, "
                "drain_v, relay, function, raw_values) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, result.timestamp, s.name, result.unit,
                 result.secondary_median, result.secondary_unit, result.n,
                 result.median, result.mean, result.std, result.minimum,
                 result.maximum, result.spread_pct, s.freq_hz, s.ac_level_v,
                 s.gate_v, s.drain_v, s.relay_state, s.lcr_function,
                 ";".join(f"{v:.6g}" for v in result.values)),
            )

    def rows(self, run_id: str) -> list[tuple]:
        with self._db() as conn:
            return conn.execute(
                "SELECT timestamp, param, unit, secondary_median, secondary_unit, n, "
                "median, mean, std, min, max, "
                "spread_pct, freq_hz, ac_level_v, gate_v, drain_v, relay, function, "
                "raw_values FROM measurements WHERE run_id=? ORDER BY id",
                (run_id,),
            ).fetchall()

    def run_info(self, run_id: str) -> dict | None:
        with self._db() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def export_csv(self, run_id: str, path: str) -> None:
        rows = self.rows(run_id)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)
            for row in rows:
                writer.writerow(row)

    def close(self) -> None:
        # 每次操作独立连接，这里无需动作；保留接口便于以后切换连接池
        pass
