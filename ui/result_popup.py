# ui/result_popup.py
"""一键测试结果弹窗"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget


class ResultPopup(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("测量结果")
        self.setMinimumSize(300, 260)
        self.setStyleSheet("background-color: #18191a;")
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("MOS 参数测试结果")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:16px;font-weight:bold;color:#C0C4C8;font-family:'SimSun';")
        layout.addWidget(title)

        self._labels = {}
        for name, unit, color in [
            ("Ciss", "pF", "#E0C860"), ("Coss", "pF", "#60C860"),
            ("Crss", "pF", "#C080E0"), ("Rg",   "Ω",  "#6080E0"),
            ("Rgs",  "Ω",  "#E08060"),
        ]:
            lbl = QLabel(f"{name}:  ---.--- {unit}")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"font-size:20px;font-weight:bold;color:{color};font-family:Consolas,monospace;")
            layout.addWidget(lbl)
            self._labels[name] = lbl

        self.setLayout(layout)

    def show_results(self, results: dict):
        for name, (val, unit) in results.items():
            if name in self._labels:
                self._labels[name].setText(f"{name}: {val:8.2f} {unit}")
        self.show()
        self.raise_()
