# Contributing

## 环境

- Python 3.10+
- PyQt5、pyserial；可选 `pyqtdarktheme`
- Windows 下建议 `.venv`，不要用系统 Python 装包

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pytest
```

## 提交前检查

```powershell
python -m pytest -q
python doctor.py
```

要求：

- 不提交 `__pycache__`、`.venv`、`*.bak_*`、`data/*.db`、`data/mos_*.csv`
- 不提交 `.env`、密钥、证书、个人绝对路径；运行参数用环境变量
- 涉及硬件的改动必须同时更新 `docs/hardware/` 或 `docs/control_logic.md`
- 不允许把 25 V 加到栅极/5 V 轨；`TH1992` 的范围校验不能删
- 新增 SCPI 命令必须注明手册页码或实测依据
- 提交信息用 `vX.Y: 一句话`，一个提交只做一件事

## 代码风格

- 4 空格缩进，行宽 ≤ 110
- 测量逻辑放 `core/`，设备驱动放 `device/`，UI 只做展示/调度
- 异常要在日志里带上下文（参数、步骤、原始响应）
- 安全动作放 `finally`，不要依赖正常路径

## 硬件安全

- 接线前先读 `docs/hardware/wiring.md`
- 上电顺序：先继电器，后电源；断电顺序：先电源，后继电器
- 100 V 漏极、5 V PCB；TH1992 CH2 给 PCB/继电器板供电，栅极接 LCR 内部 bias
- 首次上电用限流电源，确认 5 V 轨没有过压
