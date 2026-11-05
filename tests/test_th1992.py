import pytest

from device.th1992 import TH1992


def test_rejects_overvoltage_on_drain():
    with pytest.raises(ValueError):
        TH1992().output_on(120.0, 5.0)


def test_rejects_high_voltage_on_pcb_rail():
    # 板供电只有 5V，绝不能把 25V 加到 CH2
    with pytest.raises(ValueError):
        TH1992().output_on(25.0, 25.0)


def test_accepts_normal_conditions():
    # 不接硬件：send 是 no-op，只验证范围校验通过
    TH1992().output_on(25.0, 5.0)
