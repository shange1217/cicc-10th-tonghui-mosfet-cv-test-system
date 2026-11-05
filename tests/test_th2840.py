import pytest

from device.th2840 import TH2840


def test_param_pairs_use_manual_syntax():
    assert TH2840.PARAM_PAIRS["Cp-D"][0] == "CP,D"
    assert TH2840.PARAM_PAIRS["Z-Q"][0] == "Z,Q"
    assert TH2840.PARAM_PAIRS["R-X"][0] == "RS,X"


def test_average_uses_med_token():
    dev = TH2840()
    calls = []
    dev.send_scpi = lambda cmd: calls.append(cmd.cmd)
    dev.set_speed("MEDIUM")
    dev.set_average(4)
    assert calls[-1] == "APER MED,4"


def test_load_calibration_is_hard_disabled():
    dev = TH2840()
    sent = []
    dev.send_cmd = lambda cmd: sent.append(cmd)
    with pytest.raises(NotImplementedError):
        dev.calibrate_load()
    assert sent == []


def test_poll_secondary_units_for_rs_and_gp():
    dev = TH2840()
    dev.fetch = lambda: {"A": 1e-12, "B": 3.5}
    dev._current_func = "CS,RS"
    out = dev.poll()
    assert out["unit_a"] == "pF"
    assert out["unit_b"] == "Ω"

    dev._current_func = "CP,GP"
    out = dev.poll()
    assert out["unit_b"] == "S"
