# ui/calibration_widget.py
"""
校准面板: 开路 / 短路 / 负载校准
"""
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QHBoxLayout, QGroupBox,
)


class CalibrationWidget(QGroupBox):

    sig_open_cal = pyqtSignal()
    sig_short_cal = pyqtSignal()
    sig_load_cal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("「 校 · 准 」", parent)
        self._cal_running = False

        layout = QHBoxLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(4, 8, 4, 4)

        self.btn_open = self._mk("开路校准")
        self.btn_open.clicked.connect(lambda: self._emit_cal("open"))
        self.btn_short = self._mk("短路校准")
        self.btn_short.clicked.connect(lambda: self._emit_cal("short"))
        self.btn_load = self._mk("负载校准")
        self.btn_load.clicked.connect(lambda: self._emit_cal("load"))
        self.btn_load.setEnabled(False)
        self.btn_load.setToolTip("TH2840 手册未定义 CORR:LOAD 执行命令；待实机确认后再启用")

        for b in [self.btn_open, self.btn_short, self.btn_load]:
            layout.addWidget(b)
        self.setLayout(layout)

    def _emit_cal(self, cal_type: str):
        if self._cal_running:
            return  # 防抖: 校准进行中忽略重复点击
        self._cal_running = True
        for b in [self.btn_open, self.btn_short]:
            b.setEnabled(False)
        {"open": self.sig_open_cal, "short": self.sig_short_cal,
         "load": self.sig_load_cal}[cal_type].emit()

    def set_btn_text(self, cal_type: str, text: str):
        btn = {"open": self.btn_open, "short": self.btn_short, "load": self.btn_load}.get(cal_type)
        if btn:
            btn.setText(text)
        # 所有按钮重新启用
        self._cal_running = False
        for b in [self.btn_open, self.btn_short]:
            b.setEnabled(True)
        self.btn_load.setEnabled(False)

    @staticmethod
    def _mk(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(22)
        btn.setStyleSheet(
            "QPushButton { background-color: rgba(36,38,42,180); border: 1px solid rgba(255,255,255,10); "
            "color: #C8CCD0; font-size: 10px; font-weight: bold; font-family: 'SimSun', '宋体'; }"
            "QPushButton:hover { border-color: #00D8C0; color: #00D8C0; background-color: rgba(0,216,192,30); }"
            "QPushButton:pressed { background-color: rgba(0,216,192,10); }"
        )
        return btn
