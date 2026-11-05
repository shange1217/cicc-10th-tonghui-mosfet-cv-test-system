# 基于 TH1992 + TH2840E 的 MOSFET C-V 测试系统（v1.4.2）

第十届全国大学生集成电路创新创业大赛 · 同惠杯 · 队伍 **CICC 团队** 提交版。

PyQt5 上位机 + STM32 下位机 + 继电器矩阵，控制 **TH2840E LCR + TH1992 双通道源表 + STM32 十路继电器矩阵**，完成 TK9J90E 等 MOSFET 的 Ciss / Coss / Crss / Rg / Rgs 测量。

> 分赛区决赛控制逻辑：CH1=漏极、CH2=PCB +5V，栅极由 LCR 内部 bias 提供；上位机通过 SCPI 控制电桥/源表并回读；STM32 控制开关矩阵。
> 本仓库包含：上位机、固件、接线/BOM、技术文档公开摘要、测试与测量记录。
>
> 面试/评审快速导览：[PORTFOLIO.md](PORTFOLIO.md)

## 快速阅读

- 面试/评审：先看 [PORTFOLIO.md](PORTFOLIO.md)
- 安装运行：第 4 节
- 8 步流程与安全：3.1 / 3.3
- 测试：第 5 节
- 已知限制：第 6 节

## 1. 目录

```
th2840_control/
├── main.py                 入口（主题 + 高 DPI）
├── doctor.py               无仪器自检
├── PORTFOLIO.md            面试/评审导览
├── README.md               本文件
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── core/
│   ├── scpi.py             SCPI 命令集
│   ├── measurement.py      测量条件、统计、告警、CSV
│   ├── storage.py          SQLite 记录与迁移
│   ├── watchdog.py         连接看门狗
│   └── tasks.py            8 步任务 + 状态机
├── device/
│   ├── serial_device.py    QSerialPort 封装
│   ├── th2840.py           TH2840E 驱动
│   ├── th1992.py           CH1=Drain / CH2=PCB +5V
│   └── stm32.py            继电器矩阵串口控制
├── ui/
│   ├── mainwindow.py       主窗口：流程、进度、结果表、日志
│   ├── display_widget.py   大屏显示
│   ├── control_widget.py   参数面板
│   ├── calibration_widget.py
│   ├── sweep_widget.py     频率列表扫描
│   ├── result_popup.py
│   └── grid_overlay.py
├── firmware/               STM32F103C8 Keil 工程
│   ├── Project.uvprojx
│   ├── Start/              启动文件 / CMSIS
│   ├── Library/            ST 标准外设库
│   └── User/               main / relay_control / usart_comm
├── docs/
│   ├── README.md           文档索引
│   ├── control_logic.md    电源/继电器时序
│   ├── relay_truth_table.md
│   ├── test_workflow.md    8 步 Task & State Table
│   ├── requirements_traceability.md
│   ├── measurement_report.md
│   ├── hardware/           接线、BOM
│   ├── images/             架构图、界面截图
│   ├── evidence/           pytest/tag/环境/哈希/环境/哈希证据
│   └── competition/        技术文档公开摘要
├── tests/                  38 项 pytest（无硬件可跑）
├── data/README.md          数据目录说明
├── .github/workflows/ci.yml
├── requirements.txt
├── pyproject.toml
├── .gitignore
├── .gitattributes
├── 启动.bat
└── 诊断.bat
```

### 1.1 提交物清单

- 上位机：`main.py`、`core/`、`device/`、`ui/`
- 下位机：`firmware/`（Keil 工程 + `User/` 源码）
- 硬件：`docs/hardware/wiring.md`、`bom.md`、`docs/relay_truth_table.md`
- 文档：技术文档（`docs/competition/`）、测试流程、测量报告
- 测试：`tests/`，CI 见 `.github/workflows/ci.yml`

## 2. 测量模型（v1.4.2）

一次测量不再只留一个数字，而是 `MeasurementSpec` + `MeasurementResult`：

- **条件**：功能（CPD/ZTD）、频率、AC 电平、Vg（LCR bias）、Vd（TH1992 CH1）、继电器状态、备注；
- **统计**：n、中位数、均值、总体标准差、最小/最大、极差百分比；
- **原始点**：分号连接，保留在 CSV 最后一列；
- **告警**：有效点 < 5，或极差 > 10%，写入日志。

CSV 字段：

```
timestamp,param,unit,secondary_median,secondary_unit,n,median,mean,std,
min,max,spread_pct,freq_hz,ac_level_v,gate_v,drain_v,relay,function,raw_values
```

文件保存到桌面 `mos_YYYYmmdd_HHMMSS.csv`。偏置来源固定：

- **Vg**：LCR 内部 DC bias（`BIAS:VOLT`），当前给 0 V；**不是 TH1992**；
- **Vd**：TH1992 **CH1（DC_H）**，0~100 V；
- **CH2**：固定 **+5 V**，给 PCB / 继电器板供电。

`TH1992.output_drain()` / `pcb_on()` 会校验 `Vd ≤ 100 V`、`PCB 4.5~5.5 V`，防止误设。`output_on()` 的参数顺序固定为 `(drain, pcb)`。

测前自检：

- `*IDN?` 确认仪器型号；
- `CORR:OPEN:STAT?` / `CORR:SHOR:STAT?` 确认开路/短路补偿状态，未开启会在日志里明确告警。

## 3. 安全设计

- **退出断电**：`closeEvent` 先 `TH1992 output_off`，再 `STM32 all_off`，最后才关串口；
- **会话保活**：一次测试会话只开一次 CH2 PCB 5 V，阶段之间只关 CH1 漏极；继电器板由 CH2 的 5 V 供电；
- **异常断电**：校准/单测/一键/连续/扫描的 `finally` 都关漏极；急停/关窗/看门狗才全关；
- **互斥**：`_begin_busy()` 保证同一时刻只有一个长流程；
- **协作取消**：测试中按“复位”不再直接改状态机，而是置 `_cancel_requested`，采样循环在安全点抛 `MeasurementCancelled`，流程断电退出；
- **STM32 看门狗**：后台线程每 2 s 发 `STATUS`，连续 3 次失败即置位；UI `QTimer` 在事件循环可运行时执行断电（`core/watchdog.py`）。**GUI 卡死/崩溃时 UI 线程无法执行断电，TH1992 输出可能保持**；软件看门狗不能替代硬件 deadman。
- **固件看门狗**：`main.c` 增加 IWDG（约 3 s），MCU 跑飞会自动复位并重新执行 `Relay_GPIO_Init()`；复位瞬间 GPIO 为浮空输入，继电器驱动板需要下拉电阻才能保证“复位即全断”。

### 3.1 电源时序（v1.2）

```
pcb_on()                # 会话开始：CH2 = PCB +5 V
for stage:
    set_relays(stage)
    output_drain(vds)    # 只动 CH1；Ciss/Coss/Crss=25V，RG=0V
    wait(DRAIN_SETTLE_MS)
    measure()
    drain_off()          # 只关漏极，PCB 5V 不动
    relays_open()        # 继电器回开路，PCB 5V 仍保持
output_off()             # 复位/关窗/急停：CH1 先回 0V 再断，CH2 同理
```

### 3.1.1 控制逻辑与 TH1992 命令（按整理版 + 手册 V1.0.6）

- Ciss/Coss/Crss：CH1（漏极）**25 V**、CH2（PCB +5V）**5 V**；
- RG(开/短)：CH1 **0 V 且输出开启**（不是高阻断开）、CH2（PCB +5V）5 V；
- 时序：**先切继电器，再开电源；先关电源，再切继电器**；
- 复位：两个通道先回 0 V，再断开，最后继电器回开路；
- TH1992 串口结束符是 **NL(0x0A)**，不是 CRLF；输出开关命令是 `OUTP1:STAT ON/OFF`；
- 详细表见 [`docs/control_logic.md`](docs/control_logic.md)。

- `DRAIN_SETTLE_MS` 默认 **1000 ms**（100 kΩ × 1 µF 的 5~10τ），可用环境变量 `MOS_DRAIN_SETTLE_MS` 覆盖；
- `RELAY_SETTLE_MS` 默认 **50 ms**，可用 `MOS_RELAY_SETTLE_MS` 覆盖。

### 3.2 数据记录（v1.2）

每次一键/单测/连续测试生成一个 `run_id`，写入 `data/measurements.db`（SQLite）：

- `runs`：时间、类型、操作员、器件号、校准号、温湿度、状态；
- `measurements`：条件、统计量、原始点；
- CSV 仍保存到桌面，但改为从数据库导出，保证“屏幕上的”和“落盘的”是同一份数据。

运行信息从环境变量读取，避免改 UI：

| 变量 | 默认 | 说明 |
|---|---|---|
| `MOS_OPERATOR` | 当前 Windows 用户 | 操作员 |
| `MOS_DEVICE_SN` | `TK9J90E` | 被测器件编号 |
| `MOS_CALIBRATION_ID` | 空 | 校准记录编号 |
| `MOS_TEMPERATURE_C` | 空 | 环境温度 |
| `MOS_HUMIDITY_PCT` | 空 | 环境湿度 |
| `MOS_NOTE` | 空 | 备注 |

### 3.3 八步测试流程（v1.3）

主界面新增「测试流程」面板，把一次完整测试拆成 8 步：

1. 连接/自检；2. 开路校准；3. 短路校准；4–8. CISS/COSS/CRSS/RG(开)/RG(短)。

- **单步**：下拉选一步，点“执行选中”；每步仍走同一套预检；
- **进度**：`3/8 · 短路校准` + 总进度条；测量中显示 `采样 7/10`；
- **暂停/继续**：只在测量采样间生效，暂停时保持偏置/继电器；
- **停止**：当前安全点后关漏极、继电器回开路；
- **结果表**：五参数 × 主值/副值(D/θ)/单位/n/极差，常驻主界面；
- **状态机**：`idle/preflight/running/paused/stopping/error/done`，实现见 `core/tasks.py`。

详细任务表与验收标准见 [`docs/test_workflow.md`](docs/test_workflow.md)。
注意：校准步骤不可暂停（时间短且涉及继电器切换），暂停按钮只在测量步骤可用。

### 3.4 功能边界（v1.4.2）

- 本系统只做**固定偏置点**的五参数测量：Ciss/Coss/Crss 用 Vd=25 V、Vg=0 V；Rg/Rgs 用 Vd=0 V、Vg=0 V。
- **不提供 Vds 阶梯扫描 / CV 曲线绘制**；该功能已取消，原 CV 面板已删除。
- 保留 `SweepWidget` 的**频率列表扫描**（1 kHz–1 MHz），它只改变 LCR 频率，不是 Vds 阶梯扫描。

### 3.5 敏感信息

不要提交 `.env`、密钥、证书、个人绝对路径或串口白名单。运行参数用环境变量传入（`MOS_OPERATOR`、`MOS_DEVICE_SN` 等），仓库只保留无密钥的默认值。

## 4. 安装与运行

> 注意发行名：`PyQt5`、`pyserial`、可选的 `pyqtdarktheme`（import 名才是 `qdarktheme`）。
> 如果 pip 报 `No matching distribution found for qdarktheme`，说明用的是旧版 requirements，按本节重装即可。

```powershell
# 建议虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install -U pip
pip install -r requirements.txt

python main.py
```

启动失败时先跑自检（不会弹窗，只打印检查结果和完整堆栈）：

```powershell
python doctor.py        # 或双击 诊断.bat
```

`启动.bat` 等价于 `python main.py`。

### 常见启动失败

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: No module named 'PyQt5'` | 依赖装到了另一个解释器/虚拟环境 | 用 `where python` 和 `python -m pip -V` 确认是同一环境，再 `pip install -r requirements.txt` |
| `No matching distribution found for qdarktheme` | 旧 requirements 把发行名写成了 `qdarktheme` | 使用本版 `requirements.txt`（`pyqtdarktheme`） |
| `cannot import name 'MeasurementSpec'` | 只同步了部分文件 | 在项目目录 `git status`，或从备份 zip 恢复后重新同步 |
| 双击 bat 窗口一闪而过 | 启动异常 | 在项目目录执行 `python main.py` 看堆栈，或运行 `诊断.bat` |

## 5. 测试

```powershell
# 只跑测试：装 pytest 即可
pip install pytest
pytest

# 或者以可编辑模式安装（pyproject 已显式声明 packages，不会再触发 flat-layout 报错）
pip install -e ".[dev]"
pytest
```

测试覆盖：

- `list_sweep_freq` 的命令序列、点数钳位、非法区间；
- 统计量（中位数/均值/总体标准差/极差）；
- 重复性告警阈值；
- CSV 表头与逐行内容（含原始点）；
- TH1992 通道顺序与漏极 0~100 V / PCB 4.5~5.5 V 范围校验；
- SQLite 记录与 CSV 导出；
- 连接看门狗的超时/恢复；
- 8 步任务列表、状态机、进度/暂停语义。

无硬件也能跑；GUI 冒烟测试可另用 `QT_QPA_PLATFORM=offscreen`。

### 测试证据

不要只看“38 项通过”这句话，直接看原始文件：

- [`docs/evidence/pytest.txt`](docs/evidence/pytest.txt)：末行 `38 passed`；
- [`docs/evidence/pytest-collect.txt`](docs/evidence/pytest-collect.txt)：按文件统计用例数；
- [`docs/evidence/test-inventory.md`](docs/evidence/test-inventory.md)：文件 → 覆盖内容 → 需求；
- [`docs/evidence/pytest.txt`](docs/evidence/pytest.txt)：本地 `pytest` 38 passed；CI 配置见 `.github/workflows/ci.yml`，未公开前不引用运行 URL；
- [`docs/evidence/git-info.txt`](docs/evidence/git-info.txt)：tag `v1.4.2`（干净历史）；
- [`docs/evidence/environment.txt`](docs/evidence/environment.txt)：Python/PyQt5/pyserial 版本。

完整说明见 [`docs/evidence/README.md`](docs/evidence/README.md)。

## 6. 已知限制

1. **主线程 I/O 尚未根治**：串口读写、`waitForReadyRead`、`msleep` 仍在 GUI 线程，长校准期间靠 `processEvents` 维持响应；v1.3 的进度/暂停也依赖 `processEvents`，没有改成 worker 线程。彻底方案是把三个设备移到 `QThread`/`QObject` worker，用信号回传数据。
2. **两套程序未合并**：`MOS_CV_Test_System`（TH2840）与本案高度重复，尚未抽公共库。
3. **TH1992 回显握手未实现（功能缺口）**：手册 V1.0.6 5.2.1 要求仪器每收到一个字符立即回显，主机收到回显后再发下一个；当前 `SerialDevice.send_cmd/query` 一次写整条命令，没有消费回显。短命令在 115200 下通常能工作，但长命令/高负载可能丢字符或错位；尚未实现，需要实机确认。
4. **暂停只覆盖测量采样**：预检/校准步骤不可暂停（时间短、涉及继电器切换）；暂停时保持偏置和继电器，停止则回安全态。
5. **通道定义需上电核对**：代码按 CH1=漏极、CH2=PCB +5 V 实现；接线前用万用表确认 CH2 确实到 PCB/继电器板供电，栅极接 LCR 内部 bias。若实际接线不是这样，不要直接上电。
6. **负载校准不可用（功能缺口）**：TH2840 手册只定义 `CORR:LOAD:STAT`/`CORR:LOAD:TYPE`，没有 `CORR:LOAD` 执行命令。`CalibrationWidget.btn_load` 已禁用，`TH2840.calibrate_load()` 直接抛 `NotImplementedError`，不会下发 `CORR:LOAD`；开路/短路校准不受影响。
7. **无硬件 deadman（安全缺口）**：上位机崩溃或 GUI 卡死时，`ConnectionWatchdog` 的 UI 定时器无法执行断电；STM32 IWDG 只复位 MCU，不会关 TH1992。漏极/PCB 输出可能保持，必须增加硬件互锁/看门狗继电器，不能把软件看门狗当唯一保护。

## 7. 回滚

- 已初始化 git，最终版标签 `v1.4.2`；用 `git log` / `git diff` / `git checkout -- <file>` 回退；
- 不再保留 `*.bak_*` 或整包 zip，历史版本以 git 为准；
- 硬件改动前先打 tag，再接线上电。

## 8. 版本

| 版本 | 内容 |
|---|---|
| v1.0 | 原始版本：连接、校准、MOS 测试、扫描、日志 |
| v1.1 | 测量条件/统计/CSV、测前自检、互斥与取消、退出断电、死代码下线、依赖/测试/git |
| v1.1.1 | 修正 requirements 的发行名（`pyqtdarktheme`）与 pyproject 打包配置；新增 `doctor.py` / `诊断.bat` |
| v1.1.2 | LCR 驱动/串口封装、TH1992 范围校验 |
| v1.2.0 | 偏置/继电器等待可配置；CH2 会话保活；STM32 连接看门狗；SQLite 测量记录与 CSV 导出 |
| v1.2.1 | 按控制逻辑整理版与 TH1992 手册 V1.0.6 修正：RG 的 CH1 为 0 V 输出、TH1992 结束符 NL、`OUTP1:STAT`、关电先回 0 V；新增控制逻辑文档 |
| v1.3.0 | 8 步测试流程、单步执行、进度条、暂停/继续、五参数结果表、显式状态机（`core/tasks.py`）；TH1992 CH1=漏极、CH2=PCB +5V；补固件/硬件/技术文档与 CI |
| v1.3.1 | LCR 驱动类/文件改为 `TH2840`，界面/日志/预检统一 TH2840E；清理历史阶段对比说明；补充 `.env` 约束 |
| v1.3.2 | 按 TH2840 V1.3.1 手册修正 `FUNC:IMP` 参数组合、列表模式、平均次数、手动量程；目录统一为 `th2840_control`；补充 TH1992 回显问题 |
| v1.3.3 | 副参数 D/θ 写入 SQLite/CSV（旧库自动迁移）；Rg 开/短一致性告警；禁用未定义的负载校准按钮；测试增至 37 项 |
| v1.3.4 | 文档明确 TH1992 回显、负载校准两个功能缺口；取消 Vds 阶梯扫描/CV 曲线功能并删除 `_attic/cv_widget.py`；保留频率列表扫描 |
| v1.3.5 | 删除不参与运行的 `_attic` 死代码；删除误导性的 `pcb_on/pcb_off` 别名和未使用的 `_current_freq`/`set_display_mode`；修正副参数 RS/GP 单位显示 |
| v1.4.0 | 按分赛区决赛《控制逻辑》/技术文档回退 CH1=漏极、CH2=PCB +5V、栅极=LCR 内部 bias；恢复 `pcb_on/pcb_off`；同步测试与接线文档 |
| v1.4.1 | 增加 `PORTFOLIO.md`、架构图、两张界面截图；公开版清理技术文档作者/自定义元数据；准备 GitHub Release 文档包 |
| v1.4.2 | 干净历史重建：公开摘要、BOM 位号/数量/耐压、UI DEMO 截图、UTF-8 证据链；不再包含原 docx |
