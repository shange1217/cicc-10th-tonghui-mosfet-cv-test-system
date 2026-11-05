import csv
from pathlib import Path

import pytest

from core.measurement import (
    CSV_HEADER,
    MeasurementSpec,
    repeatability_warnings,
    rg_consistency_warning,
    summarize,
    write_results_csv,
)


def spec(name="Ciss"):
    return MeasurementSpec(
        name=name, lcr_function="CP,D", freq_hz=1e6, ac_level_v=0.05,
        gate_v=0.0, drain_v=25.0, relay_state="CISS", note="输入电容",
    )


def test_summarize_basic_stats():
    r = summarize(spec(), [10.0, 11.0, 12.0, 13.0, 14.0], "pF")
    assert r.n == 5
    assert r.median == 12.0
    assert r.mean == 12.0
    assert r.minimum == 10.0
    assert r.maximum == 14.0
    assert r.std == pytest.approx(1.4142135, rel=1e-6)
    assert r.spread_pct == pytest.approx(4 / 12 * 100)


def test_summarize_rejects_too_few_points():
    with pytest.raises(ValueError):
        summarize(spec(), [1.0, 2.0], "pF")


def test_spread_warning_threshold():
    r = summarize(spec(), [10.0, 10.1, 12.0, 10.2, 10.0], "pF")
    assert r.spread_pct > 10
    assert any("极差" in w for w in repeatability_warnings(r))


def test_no_warning_for_stable_points():
    r = summarize(spec(), [10.00, 10.01, 9.99, 10.00, 10.02], "pF")
    assert repeatability_warnings(r) == []


def test_condition_text_contains_conditions():
    text = summarize(spec(), [1, 1, 1], "pF").condition_text()
    assert "CP,D" in text and "1.000 MHz" in text
    assert "Vg(LCR bias)=0.0" in text
    assert "Vd(TH1992 CH1)=25.0" in text
    assert "PCB=5.0" in text


def test_secondary_value_is_persisted_in_row():
    r = summarize(spec(), [10.0, 10.1, 10.2], "pF",
                  secondary_values=[0.001, 0.0011, 0.0012], secondary_unit="")
    assert r.secondary_median == pytest.approx(0.0011)
    assert len(r.to_row()) == len(CSV_HEADER)
    assert r.to_row()[3] == "0.0011"


def test_rg_open_short_consistency_warning():
    close_open = summarize(spec("Rg"), [3.59, 3.60, 3.58], "Ω")
    close_short = summarize(spec("Rgs"), [3.58, 3.59, 3.60], "Ω")
    assert "短路态可能未真正短接" in rg_consistency_warning(close_open, close_short)

    far_short = summarize(spec("Rgs"), [0.5, 0.6, 0.7], "Ω")
    assert rg_consistency_warning(close_open, far_short) == ""


def test_csv_roundtrip():
    results = [
        summarize(spec("Ciss"), [10.0, 10.1, 10.2], "pF",
                  secondary_values=[0.001, 0.0011, 0.0012]),
        summarize(spec("Rg"), [1.0, 1.1, 1.2], "Ω"),
    ]
    path = Path(__file__).with_name("_csv_roundtrip_out.csv")
    try:
        write_results_csv(str(path), results)
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        assert rows[0] == CSV_HEADER
        assert len(rows) == 3
        assert rows[1][1] == "Ciss"
        assert rows[1][2] == "pF"
        assert rows[1][-1] == "10;10.1;10.2"
        assert rows[2][1] == "Rg"
    finally:
        path.unlink(missing_ok=True)
