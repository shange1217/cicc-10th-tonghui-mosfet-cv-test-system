# 控制逻辑（来自 `控制逻辑.pdf`）

## 1. 各状态的电源与继电器

| 状态 | TH1992 CH1（漏极 DC_H） | TH1992 CH2（PCB，5 V） | 继电器 |
|---|---|---|---|
| 开路校准 | 0 V | 5 V | 开路 |
| 短路校准 | 0 V | 5 V | 短路 |
| CISS | **25 V** | 5 V | CISS |
| COSS | **25 V** | 5 V | COSS |
| CRSS | **25 V** | 5 V | CRSS |
| RG(开) | **0 V（输出开启）** | 5 V | RGOPEN |
| RG(短) | **0 V（输出开启）** | 5 V | RGSHORT |
| 复位 | 0 V → 断开 | 0 V → 断开 | 开路 |

## 2. 时序规则

1. **先切继电器，再开电源**；
2. **先关电源，再切继电器**；
3. 每个状态测完，两个仪器回到初始状态（CH1 0 V/关，CH2 PCB 5 V，继电器开路）；
4. 故障/复位：两个通道先回 0 V，再断开，最后继电器回开路。

## 3. 测量设置

- LCR：1 MHz，AC 10–500 mV；栅极由 LCR 内部 bias 给 0 V，CH2 为 PCB +5V；
- 单点测量：每个状态记录 10 个数据，处理后显示；
- 连续测量：两个状态之间同步回开路。

## 4. 与代码的对应

| 规则 | 代码 |
|---|---|
| CH1 25 V / 0 V | `MOS_TEST_CONFIG` 的 `drain_v`；`_run_mos_test` / `_on_test_all` |
| CH2 PCB 始终 5 V | `_ensure_pcb()` 在会话开始调用；阶段间只 `_drain_off()` |
| 先继电器后电源 | 先 `set_*`，再 `output_drain()` |
| 先电源后继电器 | 先 `_drain_off()`，再 `_relays_open()` |
| 复位 | `_on_reset()` → `_outputs_off()` + `all_off()` |

> 注意：RG 状态的 CH1 是 **0 V 且输出开启**，不是高阻断开；代码用 `output_drain(0.0)`。
>
> 通道定义：CH1=漏极、CH2=PCB/继电器板 +5 V；栅极由 LCR 内部 DC bias 给 0 V。
