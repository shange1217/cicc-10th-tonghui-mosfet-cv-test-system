#!/usr/bin/env python3
"""启动自检：python doctor.py

逐项检查解释器、依赖、关键文件，并尝试在 offscreen 模式构建主窗口。
任何一步失败都会打印完整堆栈，便于直接定位“运行失败”的原因。
"""
import importlib
import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

REQUIRED_FILES = [
    "core/measurement.py",
    "core/scpi.py",
    "device/th2840.py",
    "ui/mainwindow.py",
    "resource/qss/industrial.qss",
]


def check_module(name: str) -> bool:
    try:
        module = importlib.import_module(name)
        version = getattr(module, "__version__", "")
        print(f"[OK]   {name} {version}")
        return True
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return False


def main() -> int:
    print("Python :", sys.version.split()[0], "|", sys.executable)
    print("项目目录:", ROOT)
    print()

    ok = True
    for name in ("PyQt5", "serial"):
        ok = check_module(name) and ok

    try:
        import qdarktheme  # noqa: F401
        print("[OK]   qdarktheme（可选主题）")
    except Exception:
        print("[WARN] qdarktheme 未安装，将回退到 Fusion 主题")

    print()
    for rel in REQUIRED_FILES:
        exists = os.path.exists(os.path.join(ROOT, rel))
        print(("[OK]   " if exists else "[FAIL] ") + rel)
        ok = exists and ok

    if not ok:
        print("\n结果：依赖或文件缺失，先处理上面的 FAIL。")
        return 1

    print("\n尝试构建主窗口（offscreen，不会弹窗）...")
    try:
        from PyQt5.QtWidgets import QApplication
        from ui.mainwindow import MainWindow

        app = QApplication([])
        window = MainWindow()
        print("[OK]   MainWindow 构建成功")
        window.close()
        app.quit()
    except Exception:
        print("[FAIL] 启动失败，完整堆栈：")
        traceback.print_exc()
        return 1

    print("\n结果：通过。若仍然无法启动，请把本页完整输出发我。")
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    # 直接退出：避免 PyQt 在解释器销毁阶段偶发非零退出码，干扰诊断结论
    os._exit(exit_code)
