# ui/grid_overlay.py
"""
Swiss Grid + 噪点颗粒 + 手绘电路线稿
"""
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QFont
from PyQt5.QtWidgets import QWidget


class GridOverlay(QWidget):

    GRID = 40
    SUB = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()

        C_BG = QColor(26, 29, 32)
        C_GRID_M = QColor(0, 200, 212, 25)
        C_GRID_S = QColor(255, 255, 255, 8)
        C_DOT = QColor(255, 255, 255, 10)
        C_CIRCUIT = QColor(0, 200, 212, 20)
        C_CIRCLE = QColor(0, 200, 212, 12)

        p.fillRect(0, 0, w, h, C_BG)

        # -- 全域细微噪点颗粒 (多层叠加) --
        # 层1: 细密暗点
        p.setPen(QPen(QColor(0, 0, 0, 8), 1))
        for x in range(0, w, 2):
            for y in range(0, h, 2):
                if (x * 17 + y * 31) % 19 == 0:
                    p.drawPoint(x, y)
        # 层2: 稀疏亮点
        p.setPen(QPen(QColor(255, 255, 255, 5), 1))
        for x in range(0, w, 3):
            for y in range(0, h, 3):
                if (x * 13 + y * 23) % 37 == 0:
                    p.drawPoint(x, y)
        # 层3: 随机中灰颗粒
        p.setPen(QPen(C_DOT, 1))
        for x in range(0, w, 2):
            for y in range(0, h, 2):
                if (x * 7 + y * 11) % 29 == 0:
                    p.drawPoint(x, y)

        # -- 次网格 --
        p.setPen(QPen(C_GRID_S, 0.5))
        for x in range(0, w, self.SUB):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, self.SUB):
            p.drawLine(0, y, w, y)

        # -- 主网格 --
        p.setPen(QPen(C_GRID_M, 0.8))
        for x in range(0, w, self.GRID):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, self.GRID):
            p.drawLine(0, y, w, y)

        # -- 交叉点刻度 --
        for x in range(0, w, self.GRID):
            for y in range(0, h, self.GRID):
                p.setPen(QPen(QColor(0, 200, 212, 40), 1.2))
                p.drawLine(x - 3, y, x + 3, y)
                p.drawLine(x, y - 3, x, y + 3)

        # -- 边角极简电路触点 --
        p.setPen(QPen(QColor(0, 200, 212, 15), 0.5))
        p.setBrush(Qt.NoBrush)
        for cx, cy in [(35, 35), (w - 35, 35), (40, h - 40), (w - 50, h - 50)]:
            p.drawEllipse(QRectF(cx - 6, cy - 6, 12, 12))
            p.drawLine(cx, cy - 10, cx, cy - 16)
            p.drawLine(cx, cy + 10, cx, cy + 16)
            p.drawLine(cx - 10, cy, cx - 16, cy)
            p.drawLine(cx + 10, cy, cx + 16, cy)

        # -- 破形几何圆 (部分超出模块边界, 打破全直角) --
        p.setPen(Qt.NoPen)
        # 右上方: 显示区底层
        p.setBrush(QBrush(QColor(0, 200, 212, 15)))
        p.drawEllipse(QRectF(w - 200, -60, 280, 280))
        # 右中方: 扫描区底层
        p.setBrush(QBrush(QColor(0, 200, 212, 10)))
        p.drawEllipse(QRectF(w - 180, h // 2 - 60, 240, 240))
        # 左下方: 日志区底层
        p.setBrush(QBrush(QColor(0, 200, 212, 8)))
        p.drawEllipse(QRectF(w // 2 - 60, h - 200, 200, 200))
        # 轮廓线
        p.setPen(QPen(QColor(0, 200, 212, 20), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(w - 200, -60, 280, 280))

        # -- 粗犷水印 --
        font = QFont('SimHei', 64)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(0, 200, 212, 3))
        p.drawText(QRectF(0, h // 2 - 50, w, 100), Qt.AlignCenter, "TH2840E")
