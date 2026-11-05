import csv
from pathlib import Path

import pytest

from core.measurement import MeasurementSpec, summarize
from core.storage import MeasurementStore, RunMeta


def _result(name="Ciss", unit="pF", values=(10.0, 10.1, 10.2)):
    spec = MeasurementSpec(
        name=name, lcr_function="CP,D", freq_hz=1e6, ac_level_v=0.05,
        gate_v=0.0, drain_v=25.0, relay_state="CISS", note="test",
    )
    return summarize(spec, values, unit,
                     secondary_values=(0.001, 0.0011, 0.0012),
                     secondary_unit="" if name == "Ciss" else "Ω")


def test_store_roundtrip_and_csv():
    path = Path(__file__).with_name("_test_store.db")
    path.unlink(missing_ok=True)
    try:
        store = MeasurementStore(str(path))
        run_id = store.start_run(RunMeta(operator="tester", device_sn="DUT-1",
                                         calibration_id="CAL-1"), "one_key")
        store.add_result(run_id, _result("Ciss"))
        store.add_result(run_id, _result("Rg", "Ω", (1.0, 1.1, 1.2)))
        store.finish_run(run_id, "done")

        rows = store.rows(run_id)
        assert len(rows) == 2
        assert rows[0][1] == "Ciss"
        assert rows[1][1] == "Rg"
        assert rows[0][3] == pytest.approx(0.0011)

        info = store.run_info(run_id)
        assert info["operator"] == "tester"
        assert info["device_sn"] == "DUT-1"
        assert info["status"] == "done"

        csv_path = Path(__file__).with_name("_test_store.csv")
        store.export_csv(run_id, str(csv_path))
        with open(csv_path, encoding="utf-8", newline="") as f:
            data = list(csv.reader(f))
        assert len(data) == 3
        assert data[0][1] == "param"
        assert data[1][1] == "Ciss"
        csv_path.unlink(missing_ok=True)
    finally:
        path.unlink(missing_ok=True)


def test_finish_unknown_run_is_harmless():
    path = Path(__file__).with_name("_test_store2.db")
    path.unlink(missing_ok=True)
    try:
        store = MeasurementStore(str(path))
        store.finish_run("does-not-exist", "done")
    finally:
        path.unlink(missing_ok=True)
