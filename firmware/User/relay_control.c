#include "relay_control.h"

//*********************工具函数实现 ***********************//
/**
 * @brief 毫秒级延时（适配72MHz系统时钟，精准5秒）
 * @param ms 延时毫秒数
 */
void Delay_ms(uint32_t ms)
{
    uint32_t i;
    for(; ms > 0; ms--)
    {
        for(i = 0; i< 12000; i++); // 实测5秒精准
    }
}

/**
 * @brief 设置单个继电器的状态
 * @param pin 继电器对应引脚
 * @param port 继电器对应GPIO端口
 * @param state 状态：RELAY_OFF/RELAY_ON
 */
void Relay_SetSingle(uint16_t pin, GPIO_TypeDef* port, uint8_t state)
{
    if(state == RELAY_ON)
    {
        GPIO_SetBits(port, pin);  // 高电平：吸合（闭）
    }
    else
    {
        GPIO_ResetBits(port, pin); // 低电平：释放（开）
    }
}

//*******************GPIO初始化实现 **********************//
/**
 * @brief 继电器控制GPIO初始化（PA0-PA7、PB0推挽输出）
 */
void Relay_GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStructure;
    
    // 使能GPIOA、GPIOB时钟
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOB, ENABLE);
    
    // 配置PA0-PA7为推挽输出，50MHz速度
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_0 | GPIO_Pin_1 | GPIO_Pin_2 | GPIO_Pin_3 |
                                  GPIO_Pin_4 | GPIO_Pin_5 | GPIO_Pin_6 | GPIO_Pin_7;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOA, &GPIO_InitStructure);
    
    // 配置PB0、PB1为推挽输出
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_0 | GPIO_Pin_1;
    GPIO_Init(GPIOB, &GPIO_InitStructure);

    // 初始状态：所有继电器断开，默认进入开路校准状态
    GPIO_ResetBits(GPIOA, GPIO_Pin_0 | GPIO_Pin_1 | GPIO_Pin_2 | GPIO_Pin_3 |
                          GPIO_Pin_4 | GPIO_Pin_5 | GPIO_Pin_6 | GPIO_Pin_7);
    GPIO_ResetBits(GPIOB, GPIO_Pin_0 | GPIO_Pin_1);
}

//==================== 状态切换函数实现 ====================
/**
 * @brief 切换到开路校准状态（所有继电器断开）
 */
void Relay_Set_OpenCalib(void)
{
    Relay_SetSingle(RELAY_K1_PIN, RELAY_K1_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K2_PIN, RELAY_K2_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K3_PIN, RELAY_K3_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K4_PIN, RELAY_K4_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K5_PIN, RELAY_K5_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K6_PIN, RELAY_K6_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K7_PIN, RELAY_K7_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K8_PIN, RELAY_K8_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K9_PIN, RELAY_K9_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K10_PIN, RELAY_K10_PORT, RELAY_OFF);
}

/**
 * @brief 切换到短路校准状态（仅K1吸合，其余断开）
 */
void Relay_Set_ShortCalib(void)
{
    Relay_SetSingle(RELAY_K1_PIN, RELAY_K1_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K2_PIN, RELAY_K2_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K3_PIN, RELAY_K3_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K4_PIN, RELAY_K4_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K5_PIN, RELAY_K5_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K6_PIN, RELAY_K6_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K7_PIN, RELAY_K7_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K8_PIN, RELAY_K8_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K9_PIN, RELAY_K9_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K10_PIN, RELAY_K10_PORT, RELAY_OFF);
}

/**
 * @brief 切换到CISS输入电容测量状态
 */
void Relay_Set_CISS(void)
{
    Relay_SetSingle(RELAY_K1_PIN, RELAY_K1_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K2_PIN, RELAY_K2_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K3_PIN, RELAY_K3_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K4_PIN, RELAY_K4_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K5_PIN, RELAY_K5_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K6_PIN, RELAY_K6_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K7_PIN, RELAY_K7_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K8_PIN, RELAY_K8_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K9_PIN, RELAY_K9_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K10_PIN, RELAY_K10_PORT, RELAY_OFF);
}

/**
 * @brief 切换到COSS输出电容测量状态
 */
void Relay_Set_COSS(void)
{
    Relay_SetSingle(RELAY_K1_PIN, RELAY_K1_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K2_PIN, RELAY_K2_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K3_PIN, RELAY_K3_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K4_PIN, RELAY_K4_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K5_PIN, RELAY_K5_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K6_PIN, RELAY_K6_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K7_PIN, RELAY_K7_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K8_PIN, RELAY_K8_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K9_PIN, RELAY_K9_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K10_PIN, RELAY_K10_PORT, RELAY_OFF);
}

/**
 * @brief 切换到CRSS反向传输电容测量状态
 */
void Relay_Set_CRSS(void)
{
    Relay_SetSingle(RELAY_K1_PIN, RELAY_K1_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K2_PIN, RELAY_K2_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K3_PIN, RELAY_K3_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K4_PIN, RELAY_K4_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K5_PIN, RELAY_K5_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K6_PIN, RELAY_K6_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K7_PIN, RELAY_K7_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K8_PIN, RELAY_K8_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K9_PIN, RELAY_K9_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K10_PIN, RELAY_K10_PORT, RELAY_OFF);
}

/**
 * @brief 切换到RG(开态栅极电阻)测量状态
 */
void Relay_Set_RG_Open(void)
{
    Relay_SetSingle(RELAY_K1_PIN, RELAY_K1_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K2_PIN, RELAY_K2_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K3_PIN, RELAY_K3_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K4_PIN, RELAY_K4_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K5_PIN, RELAY_K5_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K6_PIN, RELAY_K6_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K7_PIN, RELAY_K7_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K8_PIN, RELAY_K8_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K9_PIN, RELAY_K9_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K10_PIN, RELAY_K10_PORT, RELAY_ON);
}

/**
 * @brief 切换到RG(短态栅极电阻)测量状态
 */
void Relay_Set_RG_Short(void)
{
    Relay_SetSingle(RELAY_K1_PIN, RELAY_K1_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K2_PIN, RELAY_K2_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K3_PIN, RELAY_K3_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K4_PIN, RELAY_K4_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K5_PIN, RELAY_K5_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K6_PIN, RELAY_K6_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K7_PIN, RELAY_K7_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K8_PIN, RELAY_K8_PORT, RELAY_ON);
    Relay_SetSingle(RELAY_K9_PIN, RELAY_K9_PORT, RELAY_OFF);
    Relay_SetSingle(RELAY_K10_PIN, RELAY_K10_PORT, RELAY_ON);
}
