# ui/display_widget.py
"""
测量显示面板 — 仿 TH2840E 前面板
大字体显示主副参数, 底部显示设置信息
"""
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtWidgets import QLabel, QGridLayout, QGroupBox, QFrame


class DisplayWidget(QGroupBox):

    CLR_VALUE = "#00D8C0"
    CLR_UNIT  = "#889098"
    CLR_DIM   = "#505860"

    def __init__(self, parent=None):
        super().__init__("「 测量显示 」", parent)
        self.setStyleSheet("QGroupBox { border: 1px solid rgba(255,255,255,8); border-left: none; border-right: none; background-color: rgba(30,32,36,210); }"
                          "QGroupBox:hover { background-color: rgba(0,216,192,30); border-color: #00D8C0; }")
        self._setup()

    def _setup(self):
        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setContentsMargins(14, 18, 14, 10)

        big = ("font-size: 54px; font-weight: bold; color: #00c8d4; "
               "font-family: 'SimSun', '宋体';")
        mid = ("font-size: 28px; font-weight: bold; color: #B0B8C0; "
               "font-family: 'SimSun', '宋体';")
        unit = ("font-size: 20px; font-weight: bold; color: #889098; "
                "font-family: 'SimSun', '宋体';")
        label_style = ("font-size: 12px; font-weight: bold; color: #6A7888; letter-spacing: 5px; "
                       "font-family: 'SimSun', '宋体';")

        # -- 主参数行 ----------------------------------------------------
        self.lbl_a_label = QLabel("Cp")
        self.lbl_a_label.setStyleSheet(label_style)
        grid.addWidget(self.lbl_a_label, 0, 0, Qt.AlignLeft | Qt.AlignBottom)

        self.lbl_a_val = QLabel("---.---")
        self.lbl_a_val.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.lbl_a_val.setStyleSheet(big)
        grid.addWidget(self.lbl_a_val, 0, 1)

        self.lbl_a_unit = QLabel("pF")
        self.lbl_a_unit.setStyleSheet(unit)
        grid.addWidget(self.lbl_a_unit, 0, 2, Qt.AlignBottom)

        # -- 副参数行 ----------------------------------------------------
        self.lbl_b_label = QLabel("D")
        self.lbl_b_label.setStyleSheet(label_style)
        grid.addWidget(self.lbl_b_label, 1, 0, Qt.AlignLeft | Qt.AlignBottom)

        self.lbl_b_val = QLabel("-.----")
        self.lbl_b_val.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.lbl_b_val.setStyleSheet(mid)
        grid.addWidget(self.lbl_b_val, 1, 1)

        self.lbl_b_unit = QLabel("")
        self.lbl_b_unit.setStyleSheet(unit)
        grid.addWidget(self.lbl_b_unit, 1, 2, Qt.AlignBottom)

        # -- 分隔 --------------------------------------------------------
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: transparent; border-top: 1px dashed #2a3038; max-height: 1px;")
        grid.addWidget(line, 2, 0, 1, 3)

        # -- 第三行: 速度和状态 ------------------------------------------
        self.lbl_speed = QLabel("FAST")
        self.lbl_speed.setStyleSheet(f"font-size: 10px; color: {self.CLR_DIM};")
        grid.addWidget(self.lbl_speed, 3, 0, Qt.AlignLeft)

        self.lbl_freq_info = QLabel("1.0000 MHz")
        self.lbl_freq_info.setStyleSheet(f"font-size: 10px; color: {self.CLR_DIM};")
        grid.addWidget(self.lbl_freq_info, 3, 1, Qt.AlignCenter)

        self.lbl_range_info = QLabel("AUTO")
        self.lbl_range_info.setStyleSheet(f"font-size: 10px; color: {self.CLR_DIM};")
        grid.addWidget(self.lbl_range_info, 3, 2, Qt.AlignRight)

        # -- 计时器行 --
        self._lbl_timer = QLabel("00:00.0")
        self._lbl_timer.setAlignment(Qt.AlignCenter)
        self._lbl_timer.setStyleSheet("font-size: 22px; font-weight: bold; color: #808488; font-family: 'Consolas', monospace;")
        grid.addWidget(self._lbl_timer, 4, 0, 1, 3)

        self._elapsed = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        grid.setRowStretch(0, 2)
        grid.setRowStretch(1, 1)
        self.setLayout(grid)

    def _tick(self):
        from PyQt5.QtCore import QElapsedTimer
        if hasattr(self, '_clock') and self._clock.isValid():
            secs = self._clock.elapsed() / 1000.0
            m = int(secs // 60)
            s = secs % 60
            self._lbl_timer.setText(f"{m:02d}:{s:04.1f}")

    def timer_start(self):
        from PyQt5.QtCore import QElapsedTimer
        self._clock = QElapsedTimer()
        self._clock.start()
        self._lbl_timer.setText("00:00.0")
        self._timer.start(100)

    def timer_stop(self):
        self._timer.stop()

    def reset_data(self):
        self.lbl_a_val.setText("---.---")
        self.lbl_b_val.setText("-.----")
        self._elapsed = 0.0
        self._lbl_timer.setText("00:00.0")

    # -- 公开接口 ---------------------------------------------------------
    @pyqtSlot(dict)
    def update_data(self, data: dict):
        try:
            if "A" in data and data["A"] is not None:
                a = data["A"]
                if abs(a) >= 1000:
                    self.lbl_a_val.setText(f"{a:.1f}")
                elif abs(a) >= 100:
                    self.lbl_a_val.setText(f"{a:.2f}")
                elif abs(a) >= 1:
                    self.lbl_a_val.setText(f"{a:.3f}")
                else:
                    self.lbl_a_val.setText(f"{a:.4f}")
            if "B" in data and data["B"] is not None:
                self.lbl_b_val.setText(f"{data['B']:.5f}")
            if "unit_a" in data:
                self.lbl_a_unit.setText(data["unit_a"])
            if "unit_b" in data:
                self.lbl_b_unit.setText(data["unit_b"])
        except Exception:
            pass  # 单次显示更新失败不影响后续轮询

    def set_param_labels(self, primary: str, secondary: str, unit_a: str, unit_b: str):
        self.lbl_a_label.setText(primary)
        self.lbl_b_label.setText(secondary)
        self.lbl_a_unit.setText(unit_a)
        self.lbl_b_unit.setText(unit_b)

    def set_info(self, speed: str, freq: str, range_str: str):
        self.lbl_speed.setText(speed)
        self.lbl_freq_info.setText(freq)
        self.lbl_range_info.setText(range_str)
