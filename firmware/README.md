# STM32 下位机（继电器矩阵）

## 1. 硬件

- MCU：STM32F103C8T6，72 MHz；
- 10 路继电器：K1–K10，经 ULN2803 驱动；
- 串口：USART1，**115200-8-N-1**，命令以 `\n` 结束；
- 独立看门狗 IWDG 约 3 s。

## 2. 目录

```
firmware/
├── Project.uvprojx      Keil MDK 工程
├── Start/               启动文件、CMSIS
├── Library/             STM32F10x 标准外设库
├── User/
│   ├── main.c           初始化、IWDG、主循环
│   ├── relay_control.c  继电器真值表
│   ├── usart_comm.c     命令解析/回包
│   ├── stm32f10x_it.c   中断
│   └── stm32f10x_conf.h
└── DebugConfig/
```

`User/gpio_relay.c/h` 是未加入工程的旧实现，未包含在本仓库，避免误编译。

## 3. 编译

1. Keil MDK 5 + ARMCC 5.06（AC5）；
2. 打开 `Project.uvprojx`，Target `STM32F103C8`；
3. Build，下载到板子；
4. 串口 115200，发 `PING` 应回 `PONG`。

> 本机没有 ARMCC，未能本地编译；工程文件来自现场可用的 Keil 工程，改动只有 `main.c` 的 IWDG 和 `usart_comm.c` 的 `snprintf`/`volatile`/丢命令保护。

## 4. 命令

| 命令 | 动作 |
|---|---|
| `PING` | `PONG` |
| `STATUS` | 回当前继电器状态 |
| `OPEN` | 全部断开（开路） |
| `SHORT` | 短路校准 |
| `CISS` / `COSS` / `CRSS` | 对应电容测量拓扑 |
| `RGOPEN` / `RGSHORT` | Rg 开/短 |
| `ALLOFF` | 全部继电器断开 |

## 5. 继电器表

见 `docs/relay_truth_table.md`。关键：**COSS 的 K6 必须闭合**；K10 只在 RG 状态闭合。

## 6. 安全

- 复位/掉电时 GPIO 浮空，继电器驱动板必须有下拉，保证“复位即全断”；
- 固件不控制 TH1992 电压，只切继电器；上位机负责“先继电器后电源”的时序；
- 若上位机崩溃，固件看门狗会复位 MCU，但不会主动关 TH1992；需要硬件/上位机侧 deadman，当前**未实现**。软件看门狗依赖上位机事件循环，GUI 卡死时不能作为断电保护。
