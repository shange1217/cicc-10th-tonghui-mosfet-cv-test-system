import pytest

from core.scpi import TH2840_SCPI


def test_list_sweep_builds_total_freq_and_mode():
    cmds = TH2840_SCPI.list_sweep_freq(1000, 100000, 5)
    assert [c.cmd for c in cmds] == [
        "LIST:TOTAL 5",
        "LIST:FREQ 1000,25750,50500,75250,100000",
        "LIST:MODE SEQ",
    ]


def test_func_uses_manual_parameter_pairs():
    assert TH2840_SCPI.func_cpd().cmd == "FUNC:IMP CP,D"
    assert TH2840_SCPI.func_ztd().cmd == "FUNC:IMP Z,ZTD"
    assert TH2840_SCPI.func_rxd().cmd == "FUNC:IMP RS,X"


def test_average_and_range_commands():
    assert TH2840_SCPI.average("FAST", 4).cmd == "APER FAST,4"
    assert TH2840_SCPI.range_value(1000).cmd == "FUNC:IMP:RANG 1000"


def test_list_sweep_points_clamped_to_minimum():
    cmds = TH2840_SCPI.list_sweep_freq(100, 200, 1)
    assert cmds[0].cmd == "LIST:TOTAL 2"


def test_list_sweep_rejects_reversed_range():
    with pytest.raises(ValueError):
        TH2840_SCPI.list_sweep_freq(100000, 1000, 5)


def test_list_sweep_rejects_non_positive_start():
    with pytest.raises(ValueError):
        TH2840_SCPI.list_sweep_freq(0, 1000, 5)
