#ifndef __USART_COMM_H
#define __USART_COMM_H

#include "stm32f10x.h"

//==================== USART 硬件配置 ====================
// USART1: TX = PA9, RX = PA10
// 需要通过 MAX232/SP3232 等电平转换芯片连接到PC RS-232接口
#define USART_BAUDRATE      115200  // 波特率
#define USART_RX_BUF_SIZE   64      // 接收缓冲区大小

//==================== 通讯协议命令定义 ====================
// 命令格式: ASCII字符串, 以 \r\n 结尾
// 命令列表:
//   "OPEN"       - 开路校准（所有继电器断开）
//   "SHORT"      - 短路校准（仅K1吸合）
//   "CISS"       - CISS输入电容测量
//   "COSS"       - COSS输出电容测量
//   "CRSS"       - CRSS反向传输电容测量
//   "RGOPEN"     - RG(开态)栅极电阻测量
//   "RGSHORT"    - RG(短态)栅极电阻测量
//   "K1 ON"      - 单独吸合K1 (K1~K9, ON/OFF)
//   "STATUS"     - 查询当前继电器状态
//   "ALL OFF"    - 全部断开
//   "HELP"       - 显示帮助信息
//
// 响应格式:
//   "OK:<state>" - 命令执行成功
//   "ERR:<msg>"  - 命令错误
//   "STATUS:..." - 状态查询响应

//==================== 测量状态枚举 ====================
typedef enum {
    STATE_OPEN_CALIB = 0,   // 开路校准
    STATE_SHORT_CALIB,      // 短路校准
    STATE_CISS,             // CISS测量
    STATE_COSS,             // COSS测量
    STATE_CRSS,             // CRSS测量
    STATE_RG_OPEN,          // RG开态测量
    STATE_RG_SHORT,         // RG短态测量
    STATE_CUSTOM            // 自定义状态（单继电器控制）
} System_State;

//==================== 函数声明 ====================

/**
 * @brief USART1初始化：PA9(TX)/PA10(RX)，115200-8-N-1，接收中断
 */
void USART1_Comm_Init(void);

/**
 * @brief 发送单个字符
 */
void USART1_SendChar(uint8_t ch);

/**
 * @brief 发送字符串
 */
void USART1_SendString(const char* str);

/**
 * @brief 发送格式化字符串（带\r\n换行）
 */
void USART1_SendLine(const char* str);

/**
 * @brief 处理接收到的命令
 * @param cmd 接收到的命令字符串（不含\r\n）
 */
void USART1_ProcessCommand(const char* cmd);

/**
 * @brief 获取当前继电器状态描述字符串
 * @return 状态描述
 */
const char* GetCurrentStateName(void);

/**
 * @brief 获取当前系统状态枚举
 */
System_State GetCurrentState(void);

/**
 * @brief 获取接收缓冲区中新命令就绪标志
 * @return 1=有新命令, 0=无新命令
 */
uint8_t USART1_CommandReady(void);

/**
 * @brief 获取并清除就绪命令
 * @param buf 输出缓冲区
 * @param size 缓冲区大小
 * @return 1=成功获取命令, 0=无命令
 */
uint8_t USART1_GetCommand(char* buf, uint8_t size);

/**
 * @brief USART1接收中断处理函数（由USART1_IRQHandler调用）
 */
void USART1_RX_IRQHandler(void);

/**
 * @brief 导出接收缓冲区，供中断服务函数写入
 */
extern uint8_t usart1_rx_buf[USART_RX_BUF_SIZE];
extern volatile uint8_t usart1_rx_index;

#endif // __USART_COMM_H
