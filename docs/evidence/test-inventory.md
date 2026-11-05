# 测试清单（38 项）

| 测试文件 | 数量 | 覆盖内容 |
|---|---:|---|
| `tests/test_measurement.py` | 8 | 统计量、重复性告警、条件文本、D/θ 落库、Rg 开/短告警、CSV |
| `tests/test_scpi.py` | 6 | `FUNC:IMP` 参数组合、`LIST:MODE`、`APER`、`LIST` 扫描区间 |
| `tests/test_storage.py` | 2 | SQLite 记录/CSV 导出、未知 run 容错 |
| `tests/test_tasks.py` | 5 | 8 步任务、进度、暂停/恢复、停止/错误、索引钳位 |
| `tests/test_th1992.py` | 3 | 漏极/PCB 范围校验、正常条件 |
| `tests/test_th1992_power.py` | 7 | CH1/CH2 顺序、PCB 幂等、只动漏极、全关、范围 |
| `tests/test_th2840.py` | 4 | 参数组合、`APER MED`、负载校准硬禁用、副参数单位 |
| `tests/test_watchdog.py` | 3 | 连续失败、恢复、停止幂等 |
| **合计** | **38** | |

## 对应关系

| 赛题/设计点 | 测试 |
|---|---|
| TH2840E SCPI 命令 | `test_scpi.py`、`test_th2840.py` |
| TH1992 CH1/CH2 电源顺序 | `test_th1992.py`、`test_th1992_power.py` |
| Ciss/Coss/Crss/Rg 统计与 D/θ | `test_measurement.py` |
| SQLite/CSV 可追溯 | `test_storage.py` |
| 8 步任务/暂停/停止 | `test_tasks.py` |
| 连接看门狗 | `test_watchdog.py` |

## 不在测试范围内

- 真实 TH2840E/TH1992 的返回格式、触发时序；
- 继电器/夹具的接触电阻与短路动作；
- 固件在 Keil/ARMCC 下的编译与烧录；
- 100 V 漏极、5 V PCB 的实机安全验证。

完整测试函数名见 `test-names.txt`，原始输出见 `pytest.txt`。
