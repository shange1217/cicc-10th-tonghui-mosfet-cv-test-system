# device/serial_device.py
"""
通用串口设备基类 - 与 MOS_CV_Test_System 中的相同
"""
import sys, os
_SYS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SYS_ROOT not in sys.path:
    sys.path.insert(0, _SYS_ROOT)

from threading import RLock
from typing import Optional

from PyQt5 import QtCore
from PyQt5.QtCore import QThread
from PyQt5.QtSerialPort import QSerialPort

from core.scpi import CMD


class SerialDevice:

    # 命令结束符；TH1992 手册规定为 NL(0x0A)，子类可覆盖
    TERMINATOR = "\r\n"

    def __init__(self, name: str = ""):
        self.name = name
        self._serial: Optional[QSerialPort] = None
        self._lock = RLock()

    def open(self, port: str, baudrate: int = 115200) -> bool:
        with self._lock:
            # 关闭旧端口防止资源泄漏
            if self._serial is not None:
                if self._serial.isOpen():
                    self._serial.close()
                self._serial = None

            self._serial = QSerialPort(port)
            self._serial.setBaudRate(baudrate)
            self._serial.setDataBits(QSerialPort.Data8)
            self._serial.setParity(QSerialPort.NoParity)
            self._serial.setStopBits(QSerialPort.OneStop)
            self._serial.setFlowControl(QSerialPort.NoFlowControl)
            if self._serial.open(QtCore.QIODevice.ReadWrite):
                return True
            self._serial = None
            return False

    def close(self):
        with self._lock:
            if self._serial is not None and self._serial.isOpen():
                self._serial.close()
            self._serial = None

    def is_open(self) -> bool:
        return self._serial is not None and self._serial.isOpen()

    def _write_locked(self, data: bytes):
        """内部: 已持锁状态下写串口 (先清旧数据)"""
        if self._serial is not None and self._serial.isOpen():
            if self._serial.bytesAvailable():
                self._serial.readAll()
            self._serial.write(data)
            self._serial.waitForBytesWritten(50)

    def send_raw(self, data: bytes):
        with self._lock:
            self._write_locked(data)

    def send_cmd(self, cmd: str):
        self.send_raw((cmd + self.TERMINATOR).encode("utf-8"))

    def query(self, cmd: str, timeout_ms: int = 800, pump_events: bool = True) -> str:
        """原子收发: 整个 send→recv 过程加锁, 防多线程抢响应"""
        from PyQt5.QtWidgets import QApplication
        with self._lock:
            self._write_locked((cmd + self.TERMINATOR).encode("utf-8"))
            QThread.msleep(30)
            s = self._serial
            if s is None or not s.isOpen():
                return ""
            if pump_events:
                elapsed = 0
                while elapsed < timeout_ms:
                    if s.waitForReadyRead(80):
                        # 第一块到达后, 等 80ms 让后续数据到齐
                        QThread.msleep(80)
                        QApplication.processEvents()
                        data = bytes(s.readAll().data())
                        QThread.msleep(30)
                        QApplication.processEvents()
                        if s.waitForReadyRead(50):
                            data += bytes(s.readAll().data())
                        return data.decode("utf-8", errors="replace").strip()
                    QApplication.processEvents()
                    elapsed += 90
                return ""
            else:
                if s.waitForReadyRead(timeout_ms):
                    data = bytes(s.readAll().data())
                    QThread.msleep(20)
                    if s.waitForReadyRead(100):
                        data += bytes(s.readAll().data())
                    return data.decode("utf-8", errors="replace").strip()
                return ""

    def query_scpi(self, scpi_cmd) -> str:
        if isinstance(scpi_cmd, CMD):
            return self.query(scpi_cmd.cmd, scpi_cmd.timeout_ms)
        return self.query(str(scpi_cmd))

    def send_scpi(self, scpi_cmd):
        if isinstance(scpi_cmd, CMD):
            self.send_cmd(scpi_cmd.cmd)
        else:
            self.send_cmd(str(scpi_cmd))
