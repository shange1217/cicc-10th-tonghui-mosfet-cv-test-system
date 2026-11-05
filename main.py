#!/usr/bin/env python3
# main.py
"""TH2840E LCR Meter 上位机 入口"""
import sys, os
_PROJ = os.path.dirname(os.path.abspath(__file__))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

try:
    from PyQt5 import QtCore
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QFont, QColor, QPalette
except ImportError:
    print("缺少 PyQt5，请先在项目目录执行：pip install -r requirements.txt")
    print(f"当前解释器：{sys.executable}")
    raise

from ui.mainwindow import MainWindow

try:
    import qdarktheme
    HAS_DARK = True
except ImportError:
    HAS_DARK = False


def _load_qss(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def main():
    if hasattr(QtCore.Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    qss_path = os.path.join(_PROJ, "resource", "qss", "industrial.qss")
    qss = _load_qss(qss_path)

    if HAS_DARK and hasattr(qdarktheme, "setup_theme"):
        qdarktheme.setup_theme("dark", additional_qss=qss)
    elif HAS_DARK and hasattr(qdarktheme, "load_stylesheet"):
        app.setStyleSheet(qdarktheme.load_stylesheet() + "\n" + qss)
    else:
        app.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(28, 30, 31))
        palette.setColor(QPalette.WindowText, QColor(192, 195, 197))
        palette.setColor(QPalette.Base, QColor(22, 24, 25))
        palette.setColor(QPalette.Text, QColor(192, 195, 197))
        palette.setColor(QPalette.Button, QColor(42, 45, 47))
        palette.setColor(QPalette.ButtonText, QColor(192, 195, 197))
        palette.setColor(QPalette.Highlight, QColor(74, 124, 89))
        palette.setColor(QPalette.HighlightedText, QColor(28, 30, 31))
        app.setPalette(palette)
        if qss:
            app.setStyleSheet(qss)

    app.setFont(QFont("Consolas", 9))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
