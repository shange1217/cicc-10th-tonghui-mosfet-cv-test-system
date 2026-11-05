# 赛题要求 → 实现

依据技术文档（CICC 团队）与系统要求。

> **证据入口**：`docs/evidence/README.md`。  
> “38 项测试 / tag”对应 `docs/evidence/pytest.txt`、`git-info.txt`；CI 配置存在，但仓库未公开前不引用运行 URL。  
> 下表源码/测试路径在 **完整包** 中；文档包只带 `docs/evidence/` 日志，不含源码目录。

## 1. 软件要求

| 要求 | 实现 | 证据 |
|---|---|---|
| 基于 STM32 编写嵌入式软件，控制开关矩阵 | `firmware/User/main.c`、`relay_control.c`、`usart_comm.c` | Keil 工程 `firmware/Project.uvprojx`；命令表见 `firmware/README.md` |
| PC 上位机通过 SCPI 控制电桥/源表并回读 | `core/scpi.py`、`device/th2840.py`、`device/th1992.py` | `tests/test_scpi.py`、`tests/test_th1992*.py` |
| CH1=漏极、CH2=PCB +5V，栅极由 LCR 内部 bias 提供 | `device/th1992.py`：CH1=Drain、CH2=PCB +5V；`ui/mainwindow.py` 的 `_ensure_pcb()` | `tests/test_th1992_power.py`；`docs/hardware/wiring.md` |
| 控制 TH2840E 在指定频率测阻抗 | `device/th2840.py` 的 `set_function/set_frequency/set_voltage` | 默认 1 MHz、AC 50 mV；`MOS_TEST_CONFIG` |
| 回读结果，计算/显示 Ciss/Coss/Crss/Rg | `core/measurement.py`、`ui/mainwindow.py` 结果表 | `tests/test_measurement.py`；`docs/measurement_report.md` |
| 语言不限 | Python 3.10+ / PyQt5 | `README.md` |

## 2. 现场与评审要求

| 要求 | 实现 |
|---|---|
| 自带继电器矩阵与测试夹具，现场搭建 C-V 系统 | `docs/hardware/wiring.md`、`docs/hardware/bom.md`、`docs/relay_truth_table.md` |
| 按给定条件测 C-V，评分看稳定性/准确性/速度/软件流畅性 | 当前软件单次采 10 点 + 中位数/极差告警；历史表 5 次见 `measurement_report.md`；8 步流程 + 进度 + 暂停 |
| 企业提前放置设备，可提前到场调试 | `doctor.py` 无仪器自检；`MOS_*` 环境变量配置 |
| 答辩材料 | `docs/` 提供原理、接线、测试记录 |

## 3. 提交物清单

- `main.py` / `core/` / `device/` / `ui/`：上位机
- `firmware/`：STM32 Keil 工程与源码
- `docs/competition/`：技术文档、控制逻辑 PDF
- `docs/hardware/`：接线、BOM、继电器表
- `docs/measurement_report.md`：测量记录
- `tests/`：38 项自动化测试
- `README.md`、`LICENSE`、`CHANGELOG.md`

## 4. 仍然存在的问题

1. **通道接线必须核对**：代码按 CH1=漏极、CH2=PCB +5 V 实现；上电前用万用表确认 CH2 确实到 PCB/继电器板供电，栅极接 LCR 内部 bias。
2. **Rg 短路态（分析推断）**：`技术文档_公开版.md` 表 5.1 的 Rg(开)≈Rg(短)≈3.59 Ω，仅差 0.23%；据此推断短路继电器/夹具可能未真正短接，或 3.5 Ω 主要是引线/接触电阻。原文档只给数据，没有下此结论；代码已加自动告警，仍需万用表核对。
3. **两线制**：Hp/Hc/Lp/Lc 合并成两端口，pF 级靠补偿，Rg 的 3.5 Ω 需要短路扣除或四线改造。
4. **主线程 I/O**：串口/等待仍在 GUI 线程，靠 `processEvents` 维持响应；长流程建议改 worker。
5. **TH1992 回显握手未实现（功能缺口）**：手册 V1.0.6 5.2.1 要求仪器每收一个字符立即回显，主机收到回显后再发下一个；当前 `SerialDevice.send_cmd/query` 一次写整条命令，没有消费回显。短命令在 115200 下通常可用，但长命令/高负载可能丢字符或错位；尚未实现，需要实机确认。
6. **负载校准不可用（功能缺口）**：TH2840 手册只给出 `CORR:LOAD:STAT`/`CORR:LOAD:TYPE`，没有 `CORR:LOAD` 执行命令。`CalibrationWidget.btn_load` 已禁用，`TH2840.calibrate_load()` 直接抛 `NotImplementedError`，不会下发 `CORR:LOAD`；开路/短路校准不受影响。
7. **无硬件 deadman（安全缺口）**：GUI 卡死/上位机崩溃时，`ConnectionWatchdog` 的 UI 定时器无法执行断电；STM32 IWDG 只复位 MCU，不会关 TH1992。漏极/PCB 输出可能保持，需要硬件互锁/看门狗继电器。

## 5. 已取消 / 已关闭的功能

- **Vds 阶梯扫描 / CV 曲线：取消**。本系统只做固定偏置点测量；原 CV 面板和 `_attic` 死代码已删除，README 不再把它列为待办。
- **频率列表扫描：保留**。`SweepWidget` 只改变 LCR 频率（1 kHz–1 MHz），不是 Vds 阶梯扫描。
- **D/θ 落库：已完成**，SQLite/CSV 均包含 `secondary_median`/`secondary_unit`。

## 6. 证据与复现

| 声明 | 证据 |
|---|---|
| 38 项测试通过 | `docs/evidence/pytest.txt`（末行 `38 passed`） |
| 测试分布 | `docs/evidence/pytest-collect.txt`、`test-inventory.md` |
| 38 个函数名 | `docs/evidence/test-names.txt` |
| 无仪器自检通过 | `docs/evidence/doctor.txt`（`MainWindow 构建成功`） |
| 提交/标签 | `docs/evidence/git-info.txt`（`6367065`、`v1.4.1`） |
| 运行环境 | `docs/evidence/environment.txt`（Python 3.14.1 / PyQt5 5.15.2 / pyserial 3.5） |
| 关键文件哈希 | `docs/evidence/sha256sums.txt` |

复现命令：

```powershell
cd <完整包根目录>
python -m pytest -q
python doctor.py
```

> 这些证据覆盖软件层；TH2840E/TH1992 实机返回、CH2 接线、Rg 夹具仍需硬件验证。
