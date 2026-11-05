#ifndef __RELAY_CONTROL_H
#define __RELAY_CONTROL_H

#include "stm32f10x.h"

//==================== 引脚与状态宏定义 ====================
// 继电器引脚定义
#define RELAY_K1_PIN     GPIO_Pin_7
#define RELAY_K1_PORT    GPIOA
#define RELAY_K2_PIN     GPIO_Pin_6
#define RELAY_K2_PORT    GPIOA
#define RELAY_K3_PIN     GPIO_Pin_5
#define RELAY_K3_PORT    GPIOA
#define RELAY_K4_PIN     GPIO_Pin_4
#define RELAY_K4_PORT    GPIOA
#define RELAY_K5_PIN     GPIO_Pin_3
#define RELAY_K5_PORT    GPIOA
#define RELAY_K6_PIN     GPIO_Pin_2
#define RELAY_K6_PORT    GPIOA
#define RELAY_K7_PIN     GPIO_Pin_1
#define RELAY_K7_PORT    GPIOA
#define RELAY_K8_PIN     GPIO_Pin_0
#define RELAY_K8_PORT    GPIOA
#define RELAY_K9_PIN     GPIO_Pin_0
#define RELAY_K9_PORT    GPIOB
#define RELAY_K10_PIN    GPIO_Pin_1
#define RELAY_K10_PORT   GPIOB

// 继电器状态定义：OFF=释放(开)，ON=吸合(闭)
#define RELAY_OFF    0
#define RELAY_ON     1

//==================== 库函数声明 ====================
/**
 * @brief 毫秒级延时r
 * @param ms 延时毫秒数
 */
void Delay_ms(uint32_t ms);

/**
 * @brief 设置单个继电器的状态
 * @param pin 继电器对应引脚
 * @param port 继电器对应GPIO端口
 * @param state 状态：RELAY_OFF/RELAY_ON
 */
void Relay_SetSingle(uint16_t pin, GPIO_TypeDef* port, uint8_t state);

/**
 * @brief 继电器控制GPIO初始化（PA0-PA7、PB0-PB1推挽输出）
 */
void Relay_GPIO_Init(void);

/**
 * @brief 切换到开路校准状态（所有继电器断开）
 */
void Relay_Set_OpenCalib(void);

/**
 * @brief 切换到短路校准状态（仅K1吸合，其余断开）
 */
void Relay_Set_ShortCalib(void);

/**
 * @brief 切换到CISS输入电容测量状态
 */
void Relay_Set_CISS(void);

/**
 * @brief 切换到COSS输出电容测量状态
 */
void Relay_Set_COSS(void);

/**
 * @brief 切换到CRSS反向传输电容测量状态
 */
void Relay_Set_CRSS(void);

/**
 * @brief 切换到RG(开态栅极电阻)测量状态
 */
void Relay_Set_RG_Open(void);

/**
 * @brief 切换到RG(短态栅极电阻)测量状态
 */
void Relay_Set_RG_Short(void);

#endif // __RELAY_CONTROL_H
