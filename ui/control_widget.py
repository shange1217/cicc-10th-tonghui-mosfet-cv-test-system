# ui/control_widget.py
"""
TH2840E 参数控制面板
频率 / 电平 / 偏置 / 速度 / 量程 / 平均 / 触发 / 测量模式
"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QComboBox, QSpinBox, QDoubleSpinBox,
)


class ControlWidget(QWidget):

    sig_apply = pyqtSignal(dict)
    sig_function_changed = pyqtSignal(str, str)  # pair_code, label

    def __init__(self, parent=None):
        super().__init__(parent)
        self._w = {}  # widget dict
        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._build_function_group())
        layout.addWidget(self._build_param_group())
        layout.addStretch()

    # -- 测量模式 ---------------------------------------------------------
    def _build_function_group(self) -> QGroupBox:
        gb = QGroupBox("「 测量模式 」")
        layout = QHBoxLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(4, 8, 4, 4)

        self._combo_func = QComboBox()
        self._combo_func.addItems([
            "Cp-D", "Cp-Q", "Cs-D", "Cs-Q", "Cs-Rs",
            "Lp-D", "Lp-Q", "Ls-D", "Ls-Q", "Ls-Rs",
            "Z-D", "Z-Q", "R-X", "R-Q",
        ])
        self._combo_func.setCurrentText("Cp-D")
        self._combo_func.currentTextChanged.connect(self._on_func_change)
        layout.addWidget(self._combo_func)

        gb.setLayout(layout)
        return gb

    def _on_func_change(self, text: str):
        from device.th2840 import TH2840
        info = TH2840.PARAM_PAIRS.get(text, ("CP,D", ""))
        self.sig_function_changed.emit(info[0], text)

    # -- 参数设置 ---------------------------------------------------------
    def _build_param_group(self) -> QGroupBox:
        gb = QGroupBox("「 参数设置 」")
        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setContentsMargins(4, 8, 4, 4)

        row = 0
        # 频率固定 1MHz (数据手册条件)
        grid.addWidget(QLabel("频率"), row, 0)
        lbl_freq = QLabel("1 MHz"); lbl_freq.setStyleSheet("font-weight: bold; color: #b8c0a8;")
        grid.addWidget(lbl_freq, row, 1); row += 1

        for lbl, items, default, key in [
            ("电平", ["50mV","100mV","200mV","500mV","1V","2V"], "50mV", "volt"),
            ("偏置", None, None, "bias"),
            ("速度", ["FAST","MEDIUM","SLOW"], "FAST", "speed"),
            ("量程", ["AUTO"], "AUTO", "range"),
            ("平均", None, None, "avg"),
            ("触发", ["CONT","SING"], "CONT", "trig"),
        ]:
            grid.addWidget(QLabel(lbl), row, 0)
            if items is not None:
                combo = QComboBox()
                combo.addItems(items)
                combo.setCurrentText(default)
                combo.setFixedWidth(80)
                if key == "range":
                    combo.setToolTip("手动量程命令尚未确认，当前仅支持自动量程")
                grid.addWidget(combo, row, 1)
                self._w[key] = combo
            elif key == "bias":
                spin = QDoubleSpinBox()
                spin.setRange(-40, 40); spin.setValue(0.0)
                spin.setDecimals(1); spin.setFixedWidth(80)
                spin.setSuffix(" V")
                grid.addWidget(spin, row, 1)
                self._w[key] = spin
            elif key == "avg":
                spin = QSpinBox()
                spin.setRange(1, 256); spin.setValue(8)
                spin.setFixedWidth(80)
                spin.setEnabled(False)
                spin.setToolTip("平均次数命令尚未确认，暂不下发")
                grid.addWidget(spin, row, 1)
                self._w[key] = spin
            row += 1

        btn = QPushButton("应用参数")
        btn.setFixedHeight(24)
        btn.setStyleSheet(
            "QPushButton { background-color: rgba(36,38,42,180); border: 1px solid rgba(255,255,255,10); "
            "color: #C8CCD0; font-size: 10px; font-weight: bold; font-family: 'SimSun', '宋体'; }"
            "QPushButton:hover { border-color: #00D8C0; color: #00D8C0; background-color: rgba(0,216,192,30); }"
        )
        btn.clicked.connect(self._on_apply)
        grid.addWidget(btn, row, 0, 1, 2)

        gb.setLayout(grid)
        return gb

    def _on_apply(self):
        params = {
            "freq_hz": 1e6,
            "freq_str": "1 MHz",
            "volt_v": float(self._w["volt"].currentText().replace("mV","e-3").replace("V","")),
            "volt_str": self._w["volt"].currentText(),
            "bias_v": self._w["bias"].value(),
            "speed": self._w["speed"].currentText(),
            "range": self._w["range"].currentText(),
            "avg": self._w["avg"].value(),
            "trig": self._w["trig"].currentText(),
            "function": self._combo_func.currentText(),
        }
        self.sig_apply.emit(params)
