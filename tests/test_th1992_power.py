import pytest

from device.th1992 import TH1992


def make_device():
    dev = TH1992()
    calls = []
    dev.send_scpi = lambda cmd: calls.append(cmd.cmd)
    return dev, calls


def test_terminator_is_nl_per_manual():
    assert TH1992.TERMINATOR == "\n"


def test_output_on_opens_pcb_before_drain():
    dev, calls = make_device()
    dev.output_on(25.0, 5.0)
    assert calls == [
        "SOUR2:VOLT 5.000", "OUTP2:STAT ON",
        "SOUR1:VOLT 25.000", "OUTP1:STAT ON",
    ]


def test_pcb_on_is_idempotent():
    dev, calls = make_device()
    dev.pcb_on(5.0)
    dev.pcb_on(5.0)
    assert calls == ["SOUR2:VOLT 5.000", "OUTP2:STAT ON"]


def test_drain_only_does_not_touch_pcb():
    dev, calls = make_device()
    dev.pcb_on(5.0)
    calls.clear()
    dev.output_drain(10.0)
    dev.drain_off()
    assert calls == [
        "SOUR1:VOLT 10.000", "OUTP1:STAT ON",
        "SOUR1:VOLT 0.000", "OUTP1:STAT OFF",
    ]


def test_output_off_zeroes_then_disconnects():
    dev, calls = make_device()
    dev.output_off()
    assert calls == [
        "SOUR1:VOLT 0.000", "OUTP1:STAT OFF",
        "SOUR2:VOLT 0.000", "OUTP2:STAT OFF",
    ]


def test_rejects_overvoltage_on_drain():
    dev, _ = make_device()
    with pytest.raises(ValueError):
        dev.output_drain(120.0)


def test_rejects_overvoltage_on_pcb_rail():
    dev, _ = make_device()
    with pytest.raises(ValueError):
        dev.pcb_on(25.0)
