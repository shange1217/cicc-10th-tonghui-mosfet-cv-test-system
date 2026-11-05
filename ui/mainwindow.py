# ui/mainwindow.py
"""
TH2840E 上位机主窗口
"""
import sys, os, math, threading
from statistics import median as _median
_SYS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SYS_ROOT not in sys.path:
    sys.path.insert(0, _SYS_ROOT)

from datetime import datetime

from PyQt5 import QtCore
from PyQt5.QtCore import QTimer, pyqtSignal, pyqtSlot, QThread
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QGroupBox, QMessageBox, QScrollArea,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt5.QtGui import QTextCursor

from device.th2840 import TH2840
from device.stm32 import STM32
from device.th1992 import TH1992
from core.measurement import (
    MeasurementResult, MeasurementSpec, repeatability_warnings,
    rg_consistency_warning, summarize, write_results_csv,
)
from core.storage import MeasurementStore, RunMeta
from core.tasks import PARAMS, TASKS, TaskProgress, TestState
from core.watchdog import ConnectionWatchdog
from .display_widget import DisplayWidget
from .control_widget import ControlWidget
from .calibration_widget import CalibrationWidget
from .result_popup import ResultPopup
from .sweep_widget import SweepWidget
from .grid_overlay import GridOverlay


APP_TITLE = "TH2840E LCR Meter Control"
VERSION   = "v1.4.2"

# 偏置建立：100 kΩ × 1 µF = 100 ms，取 5~10τ；可用环境变量覆盖
DRAIN_SETTLE_MS = int(os.getenv("MOS_DRAIN_SETTLE_MS", "1000"))
# 继电器机械稳定
RELAY_SETTLE_MS = int(os.getenv("MOS_RELAY_SETTLE_MS", "50"))


class MeasurementCancelled(Exception):
    """用户请求取消长流程时抛出，由各流程的安全点捕获。"""


class MainWindow(QMainWindow):

    _sig_log = pyqtSignal(str)
    _sig_measure = pyqtSignal(dict)
    _sig_cal_done = pyqtSignal(str, str)  # cal_type, result

    # 参数 ↔ 单位映射
    PARAM_UNITS = {
        "Cp": "pF", "Cs": "pF", "Lp": "uH", "Ls": "uH",
        "Z": "kohm", "R": "kohm", "X": "kohm", "Rs": "ohm",
        "D": "", "Q": "",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} {VERSION}")
        self.setMinimumSize(960, 680)
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1d20; }
            QWidget { font-family: 'SimSun', '宋体'; font-size: 12px; color: #C8CCD0; background: transparent; }
            QGroupBox { font-family: 'SimSun', '宋体'; font-size: 11px; font-weight: bold; color: #889098; background-color: rgba(30,32,36,210); border: 1px solid rgba(255,255,255,8); border-left: none; border-right: none; margin-top: 10px; padding: 14px 10px 8px 10px; }
            QGroupBox:hover { background-color: rgba(0,216,192,30); border-color: #00D8C0; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px; background-color: #1a1d20; color: #00D8C0; font-size: 10px; letter-spacing: 3px; }
            QComboBox { background-color: rgba(36,38,42,230); border: 1px solid rgba(255,255,255,8); padding: 3px 8px; color: #D0D4D8; min-height: 22px; font-family: 'SimSun', '宋体'; }
            QComboBox:hover { border-color: #00D8C0; background-color: rgba(0,216,192,30); }
            QComboBox::drop-down { border: none; width: 16px; border-left: 1px solid rgba(255,255,255,6); }
            QComboBox QAbstractItemView { background-color: rgba(36,38,42,248); border: 1px solid rgba(255,255,255,8); color: #D0D4D8; selection-background-color: rgba(0,216,192,15); selection-color: #00D8C0; font-family: 'SimSun', '宋体'; }
            QPlainTextEdit { background-color: rgba(26,29,32,230); border: 1px solid #2a3038; color: #889098; font-family: 'Consolas', 'Courier New', monospace; font-size: 10px; }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: #1a1d20; width: 5px; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,8); min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #00D8C0; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QLabel { color: #C8CCD0; font-family: 'SimSun', '宋体'; background: transparent; }
            QDoubleSpinBox, QSpinBox { background-color: rgba(36,38,42,230); border: 1px solid rgba(255,255,255,8); padding: 3px 6px; color: #D0D4D8; min-height: 22px; font-family: 'SimSun', '宋体'; }
            QDoubleSpinBox:hover, QSpinBox:hover { border-color: #00D8C0; background-color: rgba(0,216,192,30); }
        """)

        # -- 仪器 ----------------------------------------------------------
        self._th2840 = TH2840()
        self._stm32 = STM32()
        self._th1992 = TH1992()

        # -- MOS 默认: Vgs=0V（LCR 内部 bias）, Vds=25V（TH1992 CH1）, f=1MHz, AC=50mV --
        # 注意：TH1992 CH2 是 PCB +5V（分赛区决赛控制逻辑），栅极用 LCR 内部 bias
        # Ciss: 输入电容(G-S间), 影响开通速度, 越大导通越慢
        # Coss: 输出电容(D-S间), 关断后参与谐振, 影响EMI
        # Crss: 反向传输电容(G-D间米勒电容), 造成开关震荡和损耗
        # Rg:   栅极电阻, 漏极悬空开路测量, 越小开关越快
        # Rgs:  栅极电阻(短路态验证)
        # 参考: tr=40ns ton=80ns tf=35ns toff=140ns dv/dt≥20V/ns(Vdd=400V,Id=9A)
        self.MOS_TEST_CONFIG = {
            "Ciss": (0.0, 25.0, "CP,D",   "CISS",    "输入电容 Vds=25V Vgs=0V"),
            "Coss": (0.0, 25.0, "CP,D",   "COSS",    "输出电容 Vds=25V Vgs=0V"),
            "Crss": (0.0, 25.0, "CP,D",   "CRSS",    "米勒电容 Vds=25V Vgs=0V"),
            "Rg":   (0.0,  0.0, "Z,ZTD",  "RGOPEN",  "栅极电阻 漏极悬空开路 Vgs=0V"),
            "Rgs":  (0.0,  0.0, "Z,ZTD",  "RGSHORT", "栅极电阻 短路验证 Vgs=0V"),
        }

        # -- 主线程轮询 (QTimer, 避免跨线程访问 QSerialPort) ----------------
        self._cal_in_progress = False
        self._cancel_requested = False
        self._paused = False
        self._results: list[MeasurementResult] = []
        self._secondary: dict[str, tuple[float, str]] = {}
        self._secondary_series: dict[str, list[float]] = {}
        self._task_progress = TaskProgress()
        self._run_id: str | None = None
        try:
            self._store = MeasurementStore(os.path.join(_SYS_ROOT, "data", "measurements.db"))
        except Exception as exc:
            # 数据库不可写时不能阻止程序启动；退化为只写 CSV
            self._store = None
            print(f"警告: 无法初始化测量数据库: {exc}")
        self._watchdog: ConnectionWatchdog | None = None
        self._watchdog_event = threading.Event()
        self._watchdog_timer = QTimer(self)
        self._watchdog_timer.timeout.connect(self._on_watchdog)
        self._watchdog_timer.start(500)
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_tick)
        self._poll_timer.start(400)          # 每 400ms 轮询一次

        # -- 信号 ----------------------------------------------------------
        self._sig_log.connect(self._append_log)
        self._sig_measure.connect(self._on_data)
        self._sig_cal_done.connect(self._on_cal_done)

        # -- UI ------------------------------------------------------------
        self._build_ui()

        # -- 启动日志 ------------------------------------------------------
        self._log("TH2840E 上位机启动")
        from PyQt5.QtSerialPort import QSerialPortInfo
        ports = [p.portName() for p in QSerialPortInfo.availablePorts()]
        self._log(f"检测到串口: {ports if ports else '(无)'}")

    # -------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # 精密网格底层 (Swiss Grid + Brutalism)
        self._grid = GridOverlay(central)
        self._grid.setGeometry(central.rect())
        central.installEventFilter(self)

        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(6, 4, 6, 4)

        # -- 左侧 (可滚动) -----------------------------------------------
        left_content = QWidget()
        left_content.setFixedWidth(400)
        ll = QVBoxLayout(left_content)
        ll.setSpacing(4); ll.setContentsMargins(0, 0, 2, 0)

        # 设备连接行
        self._build_conn_row(ll)

        self._cal_widget = CalibrationWidget()
        self._cal_widget.sig_open_cal.connect(self._on_open_cal)
        self._cal_widget.sig_short_cal.connect(self._on_short_cal)
        self._cal_widget.sig_load_cal.connect(self._on_load_cal)
        ll.addWidget(self._cal_widget)

        self._ctrl_widget = ControlWidget()
        self._ctrl_widget.sig_apply.connect(self._on_apply)
        self._ctrl_widget.sig_function_changed.connect(self._on_func_change)
        ll.addWidget(self._ctrl_widget)

        self._build_task_group(ll)

        ll.addStretch()

        # TH1992 连接行
        self._build_th1992_row(ll)

        # MOS 测试按钮组
        self._build_mos_group(ll)
        ll.addStretch()

        # 包进滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(415)
        scroll.setWidget(left_content)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        main_layout.addWidget(scroll)

        # -- 右侧 (可滚动) -----------------------------------------------
        right_content = QWidget()
        right = QVBoxLayout(right_content)
        right.setSpacing(3); right.setContentsMargins(0, 0, 0, 0)

        self._disp_widget = DisplayWidget()
        right.addWidget(self._disp_widget)

        self._lbl_result = QLabel("")
        self._lbl_result.setAlignment(QtCore.Qt.AlignCenter)
        self._lbl_result.setStyleSheet(
            "color: #b8c0a8; font-size: 12px; font-weight: bold; font-family: Consolas; "
            "background-color: #1a1c1e; border-radius: 4px; padding: 4px;")
        right.addWidget(self._lbl_result)

        self._build_result_table(right)

        self._sweep_widget2 = SweepWidget()
        self._sweep_widget2.sig_start_sweep.connect(self._on_sweep_start)
        self._sweep_widget2.sig_stop_sweep.connect(self._on_sweep_stop)
        right.addWidget(self._sweep_widget2, 1)

        right.addWidget(self._build_log())

        scroll_r = QScrollArea()
        scroll_r.setWidgetResizable(True)
        scroll_r.setWidget(right_content)
        scroll_r.setStyleSheet("QScrollArea { border: none; }")
        main_layout.addWidget(scroll_r, 1)

    def _build_conn_row(self, parent_layout):
        from PyQt5.QtWidgets import QComboBox, QPushButton
        from PyQt5.QtSerialPort import QSerialPortInfo

        # -- TH2840E 连接行 --
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        self._combo_port = QComboBox()
        self._combo_port.setFixedWidth(70)
        ports = [p.portName() for p in QSerialPortInfo.availablePorts()]
        self._combo_port.addItems(ports)

        self._combo_baud = QComboBox()
        self._combo_baud.addItems(["115200", "9600", "19200", "38400", "57600"])
        self._combo_baud.setCurrentText("115200")
        self._combo_baud.setFixedWidth(80)

        self._btn_conn = self._mk_btn("连接 TH2840E", "#2d3d3d", 100)
        self._btn_conn.clicked.connect(self._toggle_conn)

        self._lbl_conn_st = QLabel("--")
        self._lbl_conn_st.setAlignment(__import__("PyQt5.QtCore", fromlist=["Qt"]).Qt.AlignCenter)
        self._lbl_conn_st.setStyleSheet("color: #505355; font-size: 9px;")

        btn_refresh = QPushButton("⟳"); btn_refresh.setFixedSize(30,22)
        btn_refresh.setToolTip("刷新串口列表")
        btn_refresh.clicked.connect(lambda: self._fill_ports(self._combo_port))
        row1.addWidget(QLabel("TH2840E:"))
        row1.addWidget(self._combo_port)
        row1.addWidget(btn_refresh)
        row1.addWidget(self._combo_baud)
        row1.addWidget(self._btn_conn)
        row1.addWidget(self._lbl_conn_st)
        row1.addStretch()
        parent_layout.addLayout(row1)

        # -- STM32 连接行 --
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        self._combo_stm32_port = QComboBox()
        self._combo_stm32_port.setFixedWidth(70)
        self._combo_stm32_port.addItems(ports)

        self._combo_stm32_baud = QComboBox()
        self._combo_stm32_baud.addItems(["115200", "230400", "460800", "921600", "9600"])
        self._combo_stm32_baud.setCurrentText("115200")
        self._combo_stm32_baud.setFixedWidth(80)

        self._btn_stm32_conn = self._mk_btn("连接 STM32", "#4a6a9a", 100)
        self._btn_stm32_conn.clicked.connect(self._toggle_stm32)

        self._lbl_stm32_st = QLabel("--")
        self._lbl_stm32_st.setAlignment(__import__("PyQt5.QtCore", fromlist=["Qt"]).Qt.AlignCenter)
        self._lbl_stm32_st.setStyleSheet("color: #505355; font-size: 9px;")

        btn_refresh2 = QPushButton("⟳"); btn_refresh2.setFixedSize(30,22)
        btn_refresh2.setToolTip("刷新串口列表")
        btn_refresh2.clicked.connect(lambda: self._fill_ports(self._combo_stm32_port))

        row2.addWidget(QLabel("STM32:"))
        row2.addWidget(self._combo_stm32_port)
        row2.addWidget(btn_refresh2)
        row2.addWidget(self._combo_stm32_baud)
        row2.addWidget(self._btn_stm32_conn)
        row2.addWidget(self._lbl_stm32_st)
        row2.addStretch()
        parent_layout.addLayout(row2)

    @staticmethod
    def _mk_btn(text: str, bg: str, w: int) -> object:
        from PyQt5.QtWidgets import QPushButton
        btn = QPushButton(text)
        btn.setFixedWidth(w); btn.setFixedHeight(22)
        btn.setStyleSheet(
            "QPushButton { background-color: rgba(36,38,42,180); border: 1px solid rgba(255,255,255,10); "
            "color: #C8CCD0; font-size: 10px; padding: 2px 8px; font-family: 'SimSun', '宋体'; }"
            "QPushButton:hover { border-color: #00D8C0; color: #00D8C0; background-color: rgba(0,216,192,30); }"
            "QPushButton:pressed { background-color: rgba(0,216,192,60); }"
        )
        return btn

    def _build_log(self) -> QGroupBox:
        gb = QGroupBox("「 Log 」")
        l = QVBoxLayout(); l.setSpacing(1); l.setContentsMargins(4,8,4,2)
        self._txt_log = QPlainTextEdit()
        self._txt_log.setReadOnly(True); self._txt_log.setMaximumBlockCount(200)
        self._txt_log.setFixedHeight(70)
        l.addWidget(self._txt_log)
        gb.setLayout(l)
        return gb

    # ===================================================================
    # 主线程轮询
    # ===================================================================
    def _poll_tick(self):
        """QTimer 回调: 主线程安全地读取测量数据"""
        if not self._cal_in_progress and self._th2840.is_open():
            try:
                data = self._th2840.poll()
                if data:
                    self._sig_measure.emit(data)
            except Exception:
                pass  # 单次轮询失败不影响后续

    # ===================================================================
    # 日志
    # ===================================================================
    def _log(self, msg: str): self._sig_log.emit(msg)

    def _outputs_off(self):
        """急停/关窗：关漏极 + 关 5 V + 继电器回开路。"""
        try:
            if self._th1992.is_open():
                self._th1992.output_off()
        except Exception as e:
            self._log(f"⚠ TH1992 断电失败: {e}")
        try:
            if self._stm32.is_open():
                self._stm32.all_off()
        except Exception as e:
            self._log(f"⚠ STM32 回开路失败: {e}")

    def _ensure_pcb(self):
        """整个测试会话保持 CH2 +5 V，避免继电器中途掉电。"""
        try:
            if self._th1992.is_open():
                self._th1992.pcb_on(5.0)
        except Exception as e:
            self._log(f"⚠ PCB +5V 开启失败: {e}")

    def _drain_off(self):
        """只关漏极，保留 5 V 板供电。"""
        try:
            if self._th1992.is_open():
                self._th1992.drain_off()
        except Exception as e:
            self._log(f"⚠ 漏极断电失败: {e}")

    def _relays_open(self):
        """阶段结束把继电器回开路，但不关 5 V。"""
        try:
            if self._stm32.is_open():
                self._stm32.all_off()
        except Exception as e:
            self._log(f"⚠ 继电器回开路失败: {e}")

    # -- 数据记录 ---------------------------------------------------------
    def _begin_run(self, kind: str):
        self._finish_run("superseded")
        if self._store is None:
            return
        try:
            self._run_id = self._store.start_run(RunMeta.from_env(), kind)
            self._log(f"数据记录已创建: {self._run_id[:8]}…")
        except Exception as e:
            self._run_id = None
            self._log(f"⚠ 无法创建数据记录: {e}")

    def _finish_run(self, status: str = "done"):
        if not self._run_id:
            return
        try:
            self._store.finish_run(self._run_id, status)
        except Exception as e:
            self._log(f"⚠ 数据记录结束失败: {e}")
        self._run_id = None

    # -- STM32 看门狗 -----------------------------------------------------
    def _start_watchdog(self):
        self._stop_watchdog()
        self._watchdog_event.clear()
        self._watchdog = ConnectionWatchdog(
            probe=lambda: bool(self._stm32.query("STATUS", timeout_s=0.3)),
            on_lost=self._watchdog_event.set,
            interval_s=2.0,
            failures=3,
        )
        self._watchdog.start()
        self._log("STM32 看门狗已启动（2 s × 3 次）")

    def _stop_watchdog(self):
        if self._watchdog is not None:
            self._watchdog.stop()
            self._watchdog = None

    def _on_watchdog(self):
        if not self._watchdog_event.is_set():
            return
        self._watchdog_event.clear()
        self._emergency_stop("STM32 连接丢失")

    def _emergency_stop(self, reason: str):
        self._log(f"⚠ {reason}，立即断电")
        self._cancel_requested = True
        self._outputs_off()
        self._cal_in_progress = False
        self._finish_run("aborted")
        self._stop_watchdog()

    def _begin_busy(self, action: str) -> bool:
        """长流程互斥：同一时刻只允许一个校准/测试/扫描流程。"""
        if self._cal_in_progress:
            self._log(f"⚠ 已有测试在执行，忽略：{action}")
            return False
        self._cal_in_progress = True
        self._cancel_requested = False
        self._paused = False
        return True

    @pyqtSlot(str)
    def _append_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._txt_log.appendHtml(f'<span style="color:#00c8d4;">|</span> '
                                 f'<span style="color:#889098;">{ts}</span>  '
                                 f'<span style="color:#B0B8C0;">{msg}</span>')
        self._txt_log.moveCursor(QTextCursor.End)

    @pyqtSlot(dict)
    def _on_data(self, data: dict):
        self._disp_widget.update_data(data)

    # ===================================================================
    # 连接
    # ===================================================================
    def _toggle_conn(self):
        if self._th2840.is_open():
            self._th2840.close()
            self._lbl_conn_st.setText("--")
            self._lbl_conn_st.setStyleSheet("color: #505355; font-size: 9px;")
            self._btn_conn.setStyleSheet("")
            self._btn_conn.setText("连接 TH2840E")
            self._log("TH2840E: 已断开")
        else:
            port = self._combo_port.currentText()
            if not port:
                QMessageBox.warning(self, "警告", "没有可用的串口!")
                return
            baud = int(self._combo_baud.currentText())
            self._lbl_conn_st.setText("...")
            self._log(f"TH2840E: 正在连接 {port} @ {baud} ...")
            if self._th2840.open(port, baud):
                self._lbl_conn_st.setText("OK")
                self._lbl_conn_st.setStyleSheet("color: #4a7c59; font-size: 9px; font-weight: bold;")
                self._btn_conn.setText("断开")
                self._btn_conn.setStyleSheet(
                    "QPushButton { background-color: rgba(36,38,42,180); border: 1px solid rgba(255,255,255,10); "
                    "color: #C8CCD0; font-size: 10px; font-family: 'SimSun', '宋体'; }")
                self._th2840.init_device()
                self._log(f"TH2840E: 连接成功 @ {baud}")
                self._disp_widget.set_info("FAST", "1.0000 MHz", "AUTO")
            else:
                self._lbl_conn_st.setText("FAIL")
                self._lbl_conn_st.setStyleSheet("color: #8b4a4a; font-size: 9px;")
                self._log(f"TH2840E: 连接失败 ({port} @ {baud})")

    def _toggle_stm32(self):
        if self._stm32.is_open():
            self._stop_watchdog()
            self._stm32.close()
            self._lbl_stm32_st.setText("--")
            self._lbl_stm32_st.setStyleSheet("color: #505355; font-size: 9px;")
            self._btn_stm32_conn.setStyleSheet("")
            self._btn_stm32_conn.setText("连接 STM32")
            self._log("STM32: 已断开")
        else:
            port = self._combo_stm32_port.currentText()
            if not port:
                QMessageBox.warning(self, "警告", "没有可用的串口!")
                return
            baud = int(self._combo_stm32_baud.currentText())
            self._lbl_stm32_st.setText("...")
            self._log(f"STM32: 正在连接 {port} @ {baud} ...")
            if self._stm32.open(port, baud):
                self._lbl_stm32_st.setText("OK")
                self._lbl_stm32_st.setStyleSheet("color: #4a7c59; font-size: 9px; font-weight: bold;")
                self._btn_stm32_conn.setText("断开")
                self._btn_stm32_conn.setStyleSheet(
                    "QPushButton { background-color: rgba(36,38,42,180); border: 1px solid rgba(255,255,255,10); "
                    "color: #C8CCD0; font-size: 10px; font-family: 'SimSun', '宋体'; }")
                self._stm32.init_device()
                check = self._stm32.check()
                self._log(f"STM32: 连接成功 @ {baud}  |  自检: {check}")
                self._start_watchdog()
            else:
                self._lbl_stm32_st.setText("FAIL")
                self._lbl_stm32_st.setStyleSheet("color: #8b4a4a; font-size: 9px;")
                self._log(f"STM32: 连接失败 ({port} @ {baud})")

    def _build_th1992_row(self, parent):
        from PyQt5.QtWidgets import QComboBox, QPushButton
        from PyQt5.QtSerialPort import QSerialPortInfo
        row = QHBoxLayout(); row.setSpacing(4)
        self._combo_th1992_port = QComboBox(); self._combo_th1992_port.setFixedWidth(70)
        self._combo_th1992_port.addItems([p.portName() for p in QSerialPortInfo.availablePorts()])
        self._combo_th1992_baud = QComboBox()
        self._combo_th1992_baud.addItems(["115200","9600","19200","38400","57600"])
        self._combo_th1992_baud.setCurrentText("115200"); self._combo_th1992_baud.setFixedWidth(80)
        self._btn_th1992_conn = self._mk_btn("连接 TH1992", "#4a6a9a", 100)
        self._btn_th1992_conn.clicked.connect(self._toggle_th1992)
        self._lbl_th1992_st = QLabel("--")
        self._lbl_th1992_st.setStyleSheet("color: #505355; font-size: 9px;")
        btn_refresh3 = QPushButton("⟳"); btn_refresh3.setFixedSize(30,22)
        btn_refresh3.setToolTip("刷新串口列表")
        btn_refresh3.clicked.connect(lambda: self._fill_ports(self._combo_th1992_port))
        row.addWidget(QLabel("TH1992:"))
        row.addWidget(self._combo_th1992_port)
        row.addWidget(btn_refresh3)
        row.addWidget(self._combo_th1992_baud)
        row.addWidget(self._btn_th1992_conn); row.addWidget(self._lbl_th1992_st)
        row.addStretch()
        parent.addLayout(row)

    @staticmethod
    def _fill_ports(combo):
        from PyQt5.QtSerialPort import QSerialPortInfo
        current = combo.currentText()
        combo.clear()
        ports = [p.portName() for p in QSerialPortInfo.availablePorts()]
        combo.addItems(ports)
        if current in ports:
            combo.setCurrentText(current)

    def _toggle_th1992(self):
        if self._th1992.is_open():
            self._th1992.close()
            self._lbl_th1992_st.setText("--")
            self._lbl_th1992_st.setStyleSheet("color: #505355; font-size: 9px;")
            self._btn_th1992_conn.setStyleSheet("")
            self._btn_th1992_conn.setText("连接 TH1992")
            self._log("TH1992: 已断开")
        else:
            port = self._combo_th1992_port.currentText()
            if not port: QMessageBox.warning(self, "警告", "没有可用的串口!"); return
            baud = int(self._combo_th1992_baud.currentText())
            self._lbl_th1992_st.setText("...")
            self._log(f"TH1992: 正在连接 {port} @ {baud} ...")
            if self._th1992.open(port, baud):
                self._lbl_th1992_st.setText("OK")
                self._lbl_th1992_st.setStyleSheet("color: #4a7c59; font-size: 9px; font-weight: bold;")
                self._btn_th1992_conn.setText("断开")
                self._th1992.init_device()
                self._log(f"TH1992: 连接成功 @ {baud}")
            else:
                self._lbl_th1992_st.setText("FAIL")
                self._log(f"TH1992: 连接失败 ({port})")

    def _build_task_group(self, parent):
        from PyQt5.QtWidgets import QComboBox
        gb = QGroupBox("「 测试流程 」")
        v = QVBoxLayout(); v.setSpacing(3); v.setContentsMargins(4, 8, 4, 4)

        self._combo_task = QComboBox()
        for i, task in enumerate(TASKS, 1):
            self._combo_task.addItem(f"{i}. {task.title}", i - 1)
        v.addWidget(self._combo_task)

        row = QHBoxLayout(); row.setSpacing(4)
        self._btn_run_all = self._mk_btn("运行全部", "#2a3545", 78)
        self._btn_step = self._mk_btn("执行选中", "#2a3545", 78)
        self._btn_pause = self._mk_btn("暂停", "#2a352a", 70)
        self._btn_stop = self._mk_btn("停止", "#352a2a", 60)
        self._btn_run_all.clicked.connect(self._run_all_tasks)
        self._btn_step.clicked.connect(self._run_selected_task)
        self._btn_pause.clicked.connect(self._toggle_pause)
        self._btn_stop.clicked.connect(self._request_stop)
        for b in (self._btn_run_all, self._btn_step, self._btn_pause, self._btn_stop):
            row.addWidget(b)
        v.addLayout(row)

        self._task_bar = QProgressBar()
        self._task_bar.setRange(0, len(TASKS))
        self._task_bar.setValue(0)
        self._task_bar.setTextVisible(False)
        self._task_bar.setFixedHeight(10)
        v.addWidget(self._task_bar)

        self._lbl_task = QLabel("0/8 · 空闲")
        self._lbl_task.setStyleSheet("color: #889098; font-size: 10px; font-family: Consolas;")
        v.addWidget(self._lbl_task)

        gb.setLayout(v)
        parent.addWidget(gb)
        self._refresh_task_ui()

    def _build_result_table(self, parent):
        gb = QGroupBox("「 五参数结果 」")
        v = QVBoxLayout(); v.setSpacing(2); v.setContentsMargins(4, 8, 4, 4)
        self._result_table = QTableWidget(len(PARAMS), 6)
        self._result_table.setHorizontalHeaderLabels(
            ["参数", "主值", "副值(D/θ)", "单位", "n", "极差%"])
        self._result_table.verticalHeader().setVisible(False)
        self._result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._result_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._result_table.setFixedHeight(40 + 44 * len(PARAMS))
        for row, name in enumerate(PARAMS):
            for col in range(6):
                item = QTableWidgetItem(name if col == 0 else "--")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self._result_table.setItem(row, col, item)
        v.addWidget(self._result_table)
        gb.setLayout(v)
        parent.addWidget(gb)

    def _build_mos_group(self, parent):
        from PyQt5.QtWidgets import QPushButton
        gb = QGroupBox("「 MOS 测试 」")
        vbox = QVBoxLayout(); vbox.setSpacing(3)
        vbox.setContentsMargins(4, 6, 4, 3)
        tests = ["Ciss","Coss","Crss","Rg","Rgs"]
        for row_items in (tests[:3], tests[3:]):
            r = QHBoxLayout(); r.setSpacing(4)
            for name in row_items:
                btn = QPushButton(name); btn.setFixedHeight(22)
                btn.setStyleSheet(
                    "QPushButton { background-color: rgba(36,38,42,180); border: 1px solid rgba(255,255,255,10); "
                    "color: #C8CCD0; font-size: 10px; font-weight: bold; padding: 2px 10px; "
                    "font-family: 'SimSun', '宋体'; }"
                    "QPushButton:hover { border-color: #00D8C0; color: #00D8C0; background-color: rgba(0,216,192,30); }"
                    "QPushButton:pressed { background-color: rgba(0,216,192,60); }")
                btn.clicked.connect(lambda checked, n=name: self._on_mos_test(n))
                r.addWidget(btn)
            vbox.addLayout(r)
        r3 = QHBoxLayout(); r3.setSpacing(4)
        for text, color, signal in [
            ("一键","#2a3545", self._on_test_all),
            ("连续","#2a352a", self._on_continuous_test),
            ("复位","#352a2a", self._on_reset)]:
            btn = QPushButton(text); btn.setFixedHeight(22)
            btn.setStyleSheet(
                "QPushButton { background-color: rgba(36,38,42,180); border: 1px solid rgba(255,255,255,10); "
                "color: #C8CCD0; font-size: 9px; font-weight: bold; padding: 2px 8px; "
                "font-family: 'SimSun', '宋体'; }"
                "QPushButton:hover { border-color: #00D8C0; color: #00D8C0; background-color: rgba(0,216,192,30); }")
            btn.clicked.connect(signal)
            r3.addWidget(btn)
        vbox.addLayout(r3)
        gb.setLayout(vbox)
        parent.addWidget(gb)

    # ===================================================================
    # 测试流程（8 步）
    # ===================================================================
    def _refresh_task_ui(self):
        p = self._task_progress
        active = p.state in (TestState.PREFLIGHT, TestState.RUNNING,
                             TestState.PAUSED, TestState.STOPPING)
        self._btn_run_all.setEnabled(not active)
        self._btn_step.setEnabled(not active)
        self._combo_task.setEnabled(not active)
        self._btn_pause.setEnabled(p.state in (TestState.RUNNING, TestState.PAUSED)
                                   and p.current.kind == "measurement")
        self._btn_stop.setEnabled(active)
        self._btn_pause.setText("继续" if p.state is TestState.PAUSED else "暂停")
        self._task_bar.setMaximum(p.total)
        self._task_bar.setValue(0 if p.state is TestState.IDLE else p.index + 1)
        self._lbl_task.setText(p.label)

    def _set_sample_progress(self, done: int, total: int):
        if self._task_progress.state not in (TestState.RUNNING, TestState.PAUSED):
            return
        if done > 0:
            self._lbl_task.setText(f"{self._task_progress.label} · 采样 {done}/{total}")
        else:
            self._lbl_task.setText(self._task_progress.label)

    def _wait_if_paused(self):
        while self._paused and not self._cancel_requested:
            QThread.msleep(50)
            QApplication.processEvents()
        if self._cancel_requested:
            raise MeasurementCancelled("用户停止")

    def _toggle_pause(self):
        if self._task_progress.state is TestState.PAUSED:
            self._paused = False
            self._task_progress.resume()
            self._log("▶ 继续")
        elif self._task_progress.state is TestState.RUNNING:
            self._paused = True
            self._task_progress.pause()
            self._log("⏸ 已暂停（保持偏置/继电器，安全点恢复）")
        self._refresh_task_ui()

    def _request_stop(self):
        if self._task_progress.state in (TestState.PREFLIGHT, TestState.RUNNING,
                                         TestState.PAUSED):
            self._cancel_requested = True
            self._paused = False
            self._task_progress.stop()
            self._log("⏹ 已请求停止：当前安全点后断电")
            self._refresh_task_ui()

    def _clear_result_table(self):
        for row in range(len(PARAMS)):
            for col in range(1, 6):
                self._result_table.item(row, col).setText("--")

    def _warn_rg_consistency(self):
        by_name = {r.spec.name: r for r in self._results}
        if "Rg" in by_name and "Rgs" in by_name:
            msg = rg_consistency_warning(by_name["Rg"], by_name["Rgs"])
            if msg:
                self._log(f"  ⚠ {msg}")

    def _update_result_row(self, result: MeasurementResult):
        try:
            row = PARAMS.index(result.spec.name)
        except ValueError:
            return
        sec = result.secondary_median
        sec_unit = result.secondary_unit
        values = [
            result.spec.name,
            f"{result.median:.4g}",
            f"{sec:.4g}{sec_unit}" if sec is not None else "--",
            result.unit,
            str(result.n),
            f"{result.spread_pct:.1f}",
        ]
        for col, text in enumerate(values):
            self._result_table.item(row, col).setText(text)

    def _task_preflight(self):
        if not self._th2840.is_open():
            raise RuntimeError("TH2840E 未连接")
        if not self._stm32.is_open():
            raise RuntimeError("STM32 未连接")
        if not self._th1992.is_open():
            raise RuntimeError("TH1992 未连接")
        self._check_instrument()
        self._ensure_pcb()
        self._log("预检通过：TH2840E / STM32 / TH1992 均在线")

    def _do_calibration(self, kind: str) -> str:
        """校准核心动作；不负责 busy/run 生命周期。"""
        self._ensure_pcb()
        try:
            if kind == "open":
                if self._stm32.is_open():
                    self._stm32.all_off()
                QThread.msleep(RELAY_SETTLE_MS)
                if self._th1992.is_open():
                    self._th1992.output_on(0, 5)
                return self._th2840.calibrate_open(stm32=self._stm32) or ""
            if self._stm32.is_open():
                self._stm32.short_on()
            QThread.msleep(RELAY_SETTLE_MS)
            if self._th1992.is_open():
                self._th1992.output_on(0, 5)
            return self._th2840.calibrate_short(stm32=self._stm32) or ""
        finally:
            self._drain_off()
            self._relays_open()

    def _execute_task(self, task):
        if task.kind == "preflight":
            self._task_preflight()
            return
        if task.kind == "calibration":
            result = self._do_calibration(task.param)
            self._log(f"{task.title}: {result or '(无响应)'}")
            if result.startswith("FAIL:"):
                raise RuntimeError(result)
            return
        self._ensure_pcb()
        self._run_mos_test(task.param)

    def _run_all_tasks(self):
        if not self._begin_busy("全部任务"):
            return
        self._task_progress.reset()
        self._paused = False
        self._cancel_requested = False
        self._results = []
        self._secondary = {}
        self._secondary_series = {}
        self._begin_run("workflow")
        self._clear_result_table()
        status = "done"
        try:
            for i, task in enumerate(TASKS):
                if self._cancel_requested:
                    raise MeasurementCancelled("用户停止")
                self._task_progress.begin(i)
                self._refresh_task_ui()
                self._wait_if_paused()
                self._execute_task(task)
            self._warn_rg_consistency()
            self._task_progress.finish()
            if self._results:
                self._save_csv()
            self._log("全部任务完成")
        except MeasurementCancelled as e:
            status = "cancelled"
            self._log(f"⚠ 测试已停止（{e}）")
            self._task_progress.reset()
        except Exception as e:
            status = "error"
            self._task_progress.fail()
            self._log(f"⚠ 任务失败（{self._task_progress.current.title}）: {e}")
        finally:
            self._paused = False
            self._cancel_requested = False
            if status == "done":
                self._drain_off()
                self._relays_open()
            else:
                # 停止/异常：两个通道都回 0 V 再断开，继电器开路
                self._outputs_off()
            self._cal_in_progress = False
            self._finish_run(status)
            self._refresh_task_ui()

    def _run_selected_task(self):
        idx = self._combo_task.currentData()
        if idx is None:
            return
        if not self._begin_busy(f"任务 {TASKS[idx].title}"):
            return
        self._task_progress.reset()
        self._paused = False
        self._cancel_requested = False
        self._results = []
        self._secondary = {}
        self._secondary_series = {}
        self._begin_run("task")
        self._clear_result_table()
        status = "done"
        try:
            self._task_progress.begin(idx)
            self._refresh_task_ui()
            if TASKS[idx].kind != "preflight":
                # 单步也必须走同一套预检门禁
                self._task_preflight()
            self._execute_task(TASKS[idx])
            self._log(f"步骤完成：{TASKS[idx].title}")
        except MeasurementCancelled as e:
            status = "cancelled"
            self._log(f"⚠ 步骤已停止（{e}）")
        except Exception as e:
            status = "error"
            self._task_progress.fail()
            self._log(f"⚠ 步骤失败（{TASKS[idx].title}）: {e}")
        finally:
            self._paused = False
            self._cancel_requested = False
            if status == "done":
                self._drain_off()
                self._relays_open()
            else:
                self._outputs_off()
            self._cal_in_progress = False
            self._finish_run(status)
            if status in ("done", "cancelled"):
                self._task_progress.reset()
            self._refresh_task_ui()

    # ===================================================================
    # 校准
    # ===================================================================
    def _on_open_cal(self):
        if not self._th2840.is_open():
            QMessageBox.warning(self, "警告", "请先连接 TH2840E!")
            self._cal_widget.set_btn_text("open", "开路校准")
            return
        if not self._stm32.is_open():
            self._log("⚠ STM32 未连接，无法切到开路状态！请先连接 STM32")
            QMessageBox.warning(self, "警告", "STM32 未连接！\n无法控制继电器切换到开路状态。\n请先连接 STM32 再校准。")
            self._cal_widget.set_btn_text("open", "开路校准")
            return
        if not self._begin_busy("开路校准"):
            self._cal_widget.set_btn_text("open", "开路校准")
            return
        self._log("开路校准: STM32 OPEN → TH1992 上电 → 采集...")
        try:
            # 先切继电器到安全状态, 再上电
            if self._stm32.is_open():
                self._stm32.all_off()
            QThread.msleep(100)
            if self._th1992.is_open():
                self._th1992.output_on(0, 5)
            result = self._th2840.calibrate_open(stm32=self._stm32)
        except Exception as e:
            result = f"FAIL:校准异常 {e}"
        finally:
            self._outputs_off()
            self._cal_in_progress = False
        self._on_cal_done("open", result or "")

    def _on_short_cal(self):
        if not self._th2840.is_open():
            QMessageBox.warning(self, "警告", "请先连接 TH2840E!")
            self._cal_widget.set_btn_text("short", "短路校准")
            return
        if not self._stm32.is_open():
            self._log("⚠ STM32 未连接，无法切到短路状态！请先连接 STM32")
            QMessageBox.warning(self, "警告", "STM32 未连接！\n无法控制继电器切换到短路状态。\n请先连接 STM32 再校准。")
            self._cal_widget.set_btn_text("short", "短路校准")
            return
        if not self._begin_busy("短路校准"):
            self._cal_widget.set_btn_text("short", "短路校准")
            return
        self._log("短路校准: STM32 SHORT → TH1992 上电 → 采集...")
        try:
            if self._stm32.is_open():
                self._stm32.short_on()
            QThread.msleep(100)
            if self._th1992.is_open():
                self._th1992.output_on(0, 5)
            result = self._th2840.calibrate_short(stm32=self._stm32)
        except Exception as e:
            result = f"FAIL:校准异常 {e}"
        finally:
            self._outputs_off()
            self._cal_in_progress = False
        self._on_cal_done("short", result or "")

    def _on_load_cal(self):
        # 按钮已禁用；这里再兜底，避免程序化触发时进入测量流程
        self._log("⚠ 负载校准未实现：TH2840 手册没有 CORR:LOAD 执行命令")
        self._cal_widget.set_btn_text("load", "负载校准")

    @pyqtSlot(str, str)
    def _on_cal_done(self, cal_type: str, result: str):
        """主线程: 处理校准结果"""
        label = {"open": "开路", "short": "短路", "load": "负载"}.get(cal_type, cal_type)
        if result.startswith("FAIL:"):
            msg = result[5:]
            # 提取失败阶段: FAIL:<阶段> 或 FAIL:<描述>
            self._log(f"{label}校准 失败 | {msg}")
            QMessageBox.warning(self, f"{label}校准失败", msg)
        elif result.startswith("1:"):
            self._log(f"{label}校准 成功 | {result[2:]}")
        else:
            self._log(f"{label}校准 结果: {result or '(无响应)'}")
        self._cal_widget.set_btn_text(cal_type, f"{label}校准")

    # ===================================================================
    # 参数
    # ===================================================================
    def _on_func_change(self, pair_code: str, label: str):
        try:
            if self._th2840.is_open():
                self._th2840.set_function(pair_code)
            parts = label.split("-")
            primary, secondary = parts[0], parts[1] if len(parts) >= 2 else ""
            ua = self.PARAM_UNITS.get(primary, "")
            ub = self.PARAM_UNITS.get(secondary, "")
            self._disp_widget.set_param_labels(primary, secondary, ua, ub)
            self._log(f"测量模式: {label}")
        except Exception as e:
            self._log(f"切换测量模式失败: {e}")

    def _on_apply(self, params: dict):
        if not self._th2840.is_open():
            QMessageBox.warning(self, "警告", "请先连接 TH2840E!"); return
        try:
            self._th2840.apply_all(
                params["freq_hz"], params["volt_v"], params["bias_v"],
                params["speed"], params["avg"], params["trig"], params["range"],
            )
            self._disp_widget.set_info(params["speed"], params["freq_str"], params["range"])
            self._log(f"参数已应用: {params['freq_str']} {params['volt_str']} "
                      f"偏置={params['bias_v']:.1f}V {params['speed']} "
                      f"触发={params['trig']}（平均/手动量程命令未确认，未下发）")
        except Exception as e:
            self._log(f"应用失败: {e}")

    # ===================================================================
    # 扫描
    # ===================================================================
    def _on_sweep_start(self, start_hz: float, stop_hz: float, points: int):
        if not self._th2840.is_open():
            QMessageBox.warning(self, "警告", "请先连接 TH2840E!"); return
        if start_hz >= stop_hz:
            QMessageBox.warning(self, "参数错误", "起始频率必须小于终止频率!")
            self._sweep_widget2.sweep_done(); return
        if not self._begin_busy("频率扫描"):
            self._sweep_widget2.sweep_done(); return
        self._log(f"开始频率扫描: {start_hz:.0f} → {stop_hz:.0f} Hz, {points}点")
        try:
            self._th2840.setup_list_sweep(start_hz, stop_hz, points)
            data = self._th2840.fetch_sweep_data()
            if data:
                step = (stop_hz - start_hz) / (len(data) - 1) if len(data) > 1 else 0
                for i, v in enumerate(data):
                    self._sweep_widget2.add_data_point(start_hz + i * step, v)
            self._log(f"扫描完成: {len(data)} 个数据点")
        except Exception as e:
            self._log(f"扫描失败: {e}")
        finally:
            self._cal_in_progress = False
            self._sweep_widget2.sweep_done()

    def _on_sweep_stop(self):
        self._log("扫描已停止")
        self._sweep_widget2.sweep_done()

    # ===================================================================
    # MOS 测试
    # ===================================================================
    def _on_mos_test(self, param: str):
        if not self._th2840.is_open():
            QMessageBox.warning(self, "警告", "请先连接 TH2840E!"); return
        if not self._begin_busy(f"MOS {param} 测试"):
            return
        self._log(f"MOS 测试: {param} ...")
        self._begin_run("single")
        self._ensure_pcb()
        status = "done"
        try:
            self._check_instrument()
            self._run_mos_test(param)
        except MeasurementCancelled as e:
            status = "cancelled"
            self._log(f"⚠ MOS 测试已取消（{e}）")
        except Exception as e:
            status = "error"
            self._log(f"MOS 测试失败: {e}")
        finally:
            self._drain_off()
            self._cal_in_progress = False
            self._finish_run(status)

    # -- 测量条件 / 采样 / 记录 ------------------------------------------
    def _spec_for(self, param: str) -> MeasurementSpec:
        """把 UI 配置翻译成可记录、可追溯的测量条件。"""
        gate_v, drain_v, lcr_mode, relay_cmd, desc = self.MOS_TEST_CONFIG[param]
        return MeasurementSpec(
            name=param,
            lcr_function=lcr_mode,
            freq_hz=1e6,
            ac_level_v=0.05,
            gate_v=gate_v,
            drain_v=drain_v,
            relay_state=relay_cmd,
            note=desc,
        )

    def _check_instrument(self):
        """测前自检：确认仪器型号与开路/短路补偿状态。"""
        try:
            ident = self._th2840.identify()
            self._log(f"仪器: {ident or '(无应答)'}")
            if ident and not any(k in ident.upper() for k in ("TH2840E", "TH2840")):
                self._log("⚠ 仪器型号不是 TH2840E/TH2840，请确认串口选择")
        except Exception as e:
            self._log(f"⚠ 读取仪器身份失败: {e}")
        try:
            open_st, short_st = self._th2840.correction_status()
            self._log(f"补偿状态: OPEN={open_st or '?'} SHORT={short_st or '?'}")
            ok = {"1", "ON"}
            if ((open_st or "").strip().upper() not in ok
                    or (short_st or "").strip().upper() not in ok):
                self._log("⚠ 开路/短路补偿未确认开启，pF 级结果可能不可信")
        except Exception as e:
            self._log(f"⚠ 读取补偿状态失败: {e}")

    def _record(self, result: MeasurementResult):
        self._results.append(result)
        self._log(f"  {result.spec.name}: {result.median:.3f} {result.unit} "
                  f"(n={result.n}, σ={result.std:.3g}, 极差={result.spread_pct:.1f}%)")
        for warning in repeatability_warnings(result):
            self._log(f"  ⚠ {warning}")
        self._update_result_row(result)
        if self._run_id and self._store:
            try:
                self._store.add_result(self._run_id, result)
            except Exception as e:
                self._log(f"⚠ 写入数据库失败: {e}")

    def _sample_values(self, param: str, is_z: bool, points: int = 10) -> list[float]:
        """采 N 点物理值；每点都检查暂停/取消标志，并记录副参数。"""
        values: list[float] = []
        secondary: list[float] = []
        for i in range(points):
            self._wait_if_paused()
            raw = self._th2840._measure_once()
            if not raw:
                QThread.msleep(10)
                raw = self._th2840._measure_once()
            if raw:
                parts = raw.split(",")
                try:
                    if is_z:
                        z_ohm = abs(float(parts[0]))
                        theta = float(parts[1]) if len(parts) > 1 else 0
                        value = z_ohm * math.cos(math.radians(theta))
                        sec = theta
                    else:
                        value = abs(float(parts[0])) * 1e12
                        sec = float(parts[1]) if len(parts) > 1 else 0.0
                    values.append(value)
                    secondary.append(sec)
                except (ValueError, IndexError):
                    pass
            self._set_sample_progress(i + 1, points)
            QThread.msleep(5)
            QApplication.processEvents()
        self._set_sample_progress(0, 0)
        if self._cancel_requested:
            raise MeasurementCancelled(param)
        if secondary:
            self._secondary[param] = (_median(secondary), "°" if is_z else "")
            self._secondary_series[param] = list(secondary)
        return values

    def _measure(self, param: str, is_z: bool = False) -> MeasurementResult:
        self._secondary.pop(param, None)
        self._secondary_series.pop(param, None)
        values = self._sample_values(param, is_z)
        if not values:
            raise ValueError(f"{param}: 采样全部无响应")
        sec = self._secondary.get(param)
        result = summarize(
            self._spec_for(param), values, "Ω" if is_z else "pF",
            secondary_values=self._secondary_series.get(param),
            secondary_unit=sec[1] if sec else "",
        )
        self._record(result)
        return result

    def _run_mos_test(self, param: str) -> MeasurementResult:
        spec = self._spec_for(param)
        self._th2840.set_function(spec.lcr_function)
        self._th2840.set_frequency(spec.freq_hz)
        self._th2840.set_voltage(spec.ac_level_v)
        self._th2840.set_speed("FAST")
        self._th2840.set_dc_bias(spec.gate_v)   # 栅极偏置：LCR 内部 BIAS，不是 TH1992
        QThread.msleep(100)
        if self._cancel_requested:
            raise MeasurementCancelled(param)

        if self._stm32.is_open():
            getattr(self._stm32, f"set_{spec.relay_state.lower()}", self._stm32.all_off)()
        QThread.msleep(RELAY_SETTLE_MS)
        # 漏极偏置：TH1992 CH1(0~100V)；CH2 PCB +5V 由 _ensure_pcb 保持
        if self._th1992.is_open():
            if spec.drain_v > 0:
                self._th1992.output_drain(spec.drain_v)
            else:
                # 控制逻辑：RG 开/短态 CH1 为 0V
                self._th1992.output_drain(0.0)
        QThread.msleep(DRAIN_SETTLE_MS if spec.drain_v > 0 else RELAY_SETTLE_MS)
        self._log(f"  {param}: {spec.note} | {spec.condition_text()}")
        try:
            return self._measure(param, is_z=param in ("Rg", "Rgs"))
        finally:
            self._drain_off()
            self._relays_open()

    def _on_test_all(self):
        if not self._begin_busy("一键测试"):
            return
        self._log("=== 一键测试 ===")
        self._disp_widget.timer_start()
        self._results = []
        self._begin_run("one_key")
        self._ensure_pcb()
        status = "done"
        stages = [
            ("Ciss", "CP,D", "set_ciss"),
            ("Coss", "CP,D", "set_coss"),
            ("Crss", "CP,D", "set_crss"),
            ("Rg", "Z,ZTD", "set_rgopen"),
            ("Rgs", "Z,ZTD", "set_rgshort"),
        ]
        try:
            self._check_instrument()
            self._th2840.set_voltage(0.05)
            self._th2840.set_speed("FAST")

            for idx, (param, lcr_mode, relay_cmd) in enumerate(stages, 1):
                if self._cancel_requested:
                    raise MeasurementCancelled(param)
                self._log(f"  [{idx}/5] {param} ...")
                if self._stm32.is_open():
                    getattr(self._stm32, relay_cmd, self._stm32.all_off)()
                QThread.msleep(RELAY_SETTLE_MS)
                spec = self._spec_for(param)
                self._th2840.set_dc_bias(spec.gate_v)   # 栅极偏置：LCR 内部 BIAS
                if self._th1992.is_open():
                    if spec.drain_v > 0:
                        self._th1992.output_drain(spec.drain_v)
                    else:
                        # 控制逻辑：RG 开/短态 CH1 为 0V（输出开启，不是高阻断开）
                        self._th1992.output_drain(0.0)
                QThread.msleep(DRAIN_SETTLE_MS if spec.drain_v > 0 else RELAY_SETTLE_MS)
                self._th2840.set_function(lcr_mode)
                self._th2840.set_frequency(1e6)
                QThread.msleep(100)
                try:
                    self._measure(param, is_z=param in ("Rg", "Rgs"))
                except ValueError as e:
                    self._log(f"  ⚠ {e}，跳过该项")
                self._drain_off()
                self._relays_open()
                QThread.msleep(200)

            if self._results:
                self._warn_rg_consistency()
                self._log("=== 一键测试完成 ===")
                self._save_csv()
                popup = ResultPopup(self)
                popup.show_results({r.spec.name: (r.median, r.unit) for r in self._results})
            else:
                self._log("=== 一键测试结束：没有有效结果 ===")
        except MeasurementCancelled as e:
            status = "cancelled"
            self._log(f"⚠ 一键测试已取消（{e}）")
        except Exception as e:
            status = "error"
            self._log(f"一键测试异常: {e}")
        finally:
            self._drain_off()
            self._cal_in_progress = False
            self._disp_widget.timer_stop()
            self._finish_run(status)

    def _on_continuous_test(self):
        if not self._begin_busy("连续测试"):
            return
        self._log("=== 连续测量 5 项 (项间开路) ===")
        self._results = []
        self._begin_run("continuous")
        self._ensure_pcb()
        status = "done"
        try:
            self._check_instrument()
            for param in ["Ciss", "Coss", "Crss", "Rg", "Rgs"]:
                if self._cancel_requested:
                    raise MeasurementCancelled(param)
                self._run_mos_test(param)
                self._drain_off()
                self._log("  --- 开路状态 ---")
                QThread.msleep(100)
            if self._results:
                self._save_csv()
        except MeasurementCancelled as e:
            status = "cancelled"
            self._log(f"⚠ 连续测试已取消（{e}）")
        except Exception as e:
            status = "error"
            self._log(f"连续测试异常: {e}")
        finally:
            self._drain_off()
            self._cal_in_progress = False
            self._finish_run(status)

    def _on_reset(self):
        if self._cal_in_progress:
            # 不再直接改状态机，而是置取消标志，由采样循环在安全点退出
            self._cancel_requested = True
            self._log("⚠ 已请求取消：当前采样结束后断电并退出")
            return
        self._log("复位: 断电 → 开路 → 数据归零")
        self._disp_widget.timer_stop()
        self._disp_widget.reset_data()
        self._outputs_off()
        self._task_progress.reset()
        self._paused = False
        self._refresh_task_ui()
        self._log("复位完成")

    def _save_csv(self):
        if not self._results:
            self._log("没有可保存的测量结果")
            return
        save_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        os.makedirs(save_dir, exist_ok=True)
        filename = os.path.join(save_dir, f"mos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        try:
            if self._run_id and self._store:
                self._store.export_csv(self._run_id, filename)
            else:
                write_results_csv(filename, self._results)
            self._log(f"数据已保存: {os.path.basename(filename)}"
                      f"（{len(self._results)} 条，含测试条件与原始点）")
        except Exception as e:
            self._log(f"保存失败: {e}")

    # ===================================================================
    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if event.type() == QEvent.Resize and hasattr(self, '_grid'):
            self._grid.setGeometry(self.centralWidget().rect())
        return False

    def closeEvent(self, event):
        self._poll_timer.stop()
        self._watchdog_timer.stop()
        self._cancel_requested = True
        self._paused = False
        self._stop_watchdog()
        self._finish_run("aborted")
        # 关窗/退出前先断源表输出，再断串口；否则输出可能一直保持
        self._outputs_off()
        try:
            self._th2840.close()
        finally:
            try:
                self._stm32.close()
            finally:
                self._th1992.close()
        if self._store:
            self._store.close()
        event.accept()
