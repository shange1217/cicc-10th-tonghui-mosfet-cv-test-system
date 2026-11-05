# ui/sweep_widget.py
"""
列表扫描面板: 频率扫描参数设置  ← 新增于 TH2840E
"""
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QDoubleSpinBox, QSpinBox, QPlainTextEdit,
)


class SweepWidget(QGroupBox):

    sig_start_sweep = pyqtSignal(float, float, int)  # start_hz, stop_hz, points
    sig_stop_sweep = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("「 列表扫描 」", parent)
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(4, 8, 4, 4)

        grid = QGridLayout()
        grid.setSpacing(2)

        grid.addWidget(QLabel("起始频率"), 0, 0)
        self._spin_start = QDoubleSpinBox()
        self._spin_start.setRange(20, 1e6); self._spin_start.setValue(1000)
        self._spin_start.setDecimals(0); self._spin_start.setFixedWidth(80)
        self._spin_start.setSuffix(" Hz")
        grid.addWidget(self._spin_start, 0, 1)

        grid.addWidget(QLabel("终止频率"), 1, 0)
        self._spin_stop = QDoubleSpinBox()
        self._spin_stop.setRange(20, 1e6); self._spin_stop.setValue(100000)
        self._spin_stop.setDecimals(0); self._spin_stop.setFixedWidth(80)
        self._spin_stop.setSuffix(" Hz")
        grid.addWidget(self._spin_stop, 1, 1)

        grid.addWidget(QLabel("扫描点数"), 2, 0)
        self._spin_points = QSpinBox()
        self._spin_points.setRange(2, 201); self._spin_points.setValue(50)
        self._spin_points.setFixedWidth(80)
        grid.addWidget(self._spin_points, 2, 1)

        layout.addLayout(grid)

        row = QHBoxLayout()
        row.setSpacing(4)
        self._btn_start = QPushButton("开始扫描")
        self._btn_start.setFixedHeight(22)
        self._btn_start.setStyleSheet(
            "QPushButton { background-color: rgba(36,38,42,180); border: 1px solid rgba(255,255,255,10); "
            "color: #C8CCD0; font-size: 10px; font-weight: bold; font-family: 'SimSun', '宋体'; }"
            "QPushButton:hover { border-color: #00D8C0; color: #00D8C0; background-color: rgba(0,216,192,30); }"
            "QPushButton:pressed { background-color: rgba(0,216,192,10); }"
        )
        self._btn_start.clicked.connect(self._on_start)
        row.addWidget(self._btn_start)

        self._btn_stop = QPushButton("停止")
        self._btn_stop.setFixedHeight(22)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setStyleSheet(
            "QPushButton { background-color: rgba(36,38,42,180); border: 1px solid rgba(255,255,255,10); "
            "color: #C8CCD0; font-size: 10px; font-family: 'SimSun', '宋体'; }"
            "QPushButton:hover { border-color: #00D8C0; background-color: rgba(0,216,192,30); }"
        )
        self._btn_stop.clicked.connect(lambda: self.sig_stop_sweep.emit())
        row.addWidget(self._btn_stop)
        layout.addLayout(row)

        self._txt_data = QPlainTextEdit()
        self._txt_data.setReadOnly(True)
        self._txt_data.setMaximumBlockCount(200)
        self._txt_data.setFixedHeight(60)
        self._txt_data.setPlaceholderText("扫描数据...")
        layout.addWidget(self._txt_data)

        self.setLayout(layout)

    def _on_start(self):
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._txt_data.clear()
        self.sig_start_sweep.emit(
            self._spin_start.value(),
            self._spin_stop.value(),
            self._spin_points.value(),
        )

    def add_data_point(self, freq: float, value: float):
        self._txt_data.appendPlainText(f"{freq:10.1f} Hz  →  {value:.5f}")

    def sweep_done(self):
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
