# device/stm32.py
"""
STM32 继电器控制器 (pyserial + 互斥锁 + 应答读取)
"""
import serial
import time
from threading import Lock


class STM32:
    """STM32 继电器控制板"""

    def __init__(self):
        self.name = "STM32"
        self._ser = None
        self._lock = Lock()

    # -- 连接管理 ---------------------------------------------------------
    def open(self, port: str, baudrate: int = 115200) -> bool:
        with self._lock:
            self._close_locked()
            try:
                self._ser = serial.Serial(port, baudrate, timeout=0.5)
                time.sleep(0.7)
                self._ser.reset_input_buffer()
                self._ser.write(b"OPEN\r\n")
                self._ser.flush()
                time.sleep(0.3)
                reply = self._ser.read_all().decode("utf-8", errors="replace").strip()
                self._last_check = reply if reply else "(无应答)"
                if not reply:
                    self._ser.close()
                    self._ser = None
                    return False
                return True
            except Exception as e:
                self._ser = None
                self._last_check = str(e)
                return False

    def close(self):
        with self._lock:
            self._close_locked()

    def _close_locked(self):
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None

    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def check(self) -> str:
        return getattr(self, '_last_check', '')

    def init_device(self) -> bool:
        return True

    # -- 命令收发 ---------------------------------------------------------
    def query(self, cmd: str, timeout_s: float = 0.3) -> str:
        """发送命令并读取应答 (持锁, 过滤心跳包)"""
        with self._lock:
            if not self._ser or not self._ser.is_open:
                return ""
            self._ser.reset_input_buffer()
            self._ser.write((cmd + "\r\n").encode("utf-8"))
            self._ser.flush()
            time.sleep(timeout_s)
            raw = self._ser.read_all().decode("utf-8", errors="replace").strip()
            lines = raw.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("OK:") or line.startswith("ERR:"):
                    return line
                if line.startswith("HEARTBEAT"):
                    continue
            for line in lines:
                line = line.strip()
                if line and not line.startswith("HEARTBEAT") and not line.startswith("INFO"):
                    return line
            return raw if raw else ""

    def send_cmd(self, cmd: str):
        """仅发送, 不读应答 (持锁)"""
        with self._lock:
            if self._ser and self._ser.is_open:
                self._ser.write((cmd + "\r\n").encode("utf-8"))
                self._ser.flush()

    # -- 继电器控制 (带应答读取) ------------------------------------------
    def all_off(self) -> str:
        return self.query("OPEN")

    def short_on(self) -> str:
        return self.query("SHORT")

    def set_ciss(self) -> str:
        return self.query("CISS")

    def set_coss(self) -> str:
        return self.query("COSS")

    def set_crss(self) -> str:
        return self.query("CRSS")

    def set_rgopen(self) -> str:
        return self.query("RGOPEN")

    def set_rgshort(self) -> str:
        return self.query("RGSHORT")
