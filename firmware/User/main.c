#include "stm32f10x.h"
#include "stm32f10x_iwdg.h"  // 独立看门狗：MCU 跑飞时复位，GPIO 复位态=继电器全断
#include "relay_control.h"   // 继电器控制库
#include "usart_comm.h"      // RS-232串口通讯模块

// 心跳包间隔（循环次数近似值，实际间隔取决于系统时钟）
// 72MHz下约等于5秒发送一次
#define HEARTBEAT_INTERVAL  30000000

// 看门狗约 3 秒：LSI 40kHz / 64 = 625Hz，1875 / 625 = 3s
#define IWDG_RELOAD_3S      1875

/**
 * @brief 独立看门狗初始化
 * @note  MCU 卡死超过约 3 秒会复位；复位后程序重新执行 Relay_GPIO_Init()，
 *        把继电器拉回开路。复位瞬间 GPIO 是浮空输入，继电器驱动板最好有下拉电阻，
 *        否则“复位即全断”不能只靠软件保证。
 */
static void IWDG_Init(void)
{
    IWDG_WriteAccessCmd(IWDG_WriteAccess_Enable);
    IWDG_SetPrescaler(IWDG_Prescaler_64);
    IWDG_SetReload(IWDG_RELOAD_3S);
    IWDG_ReloadCounter();
    IWDG_Enable();
}


/**
 * @brief PC13 LED闪烁指示（STM32F103C8最小系统板板载LED）
 */
static void LED_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStructure;
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOC, ENABLE);
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_13;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_2MHz;
    GPIO_Init(GPIOC, &GPIO_InitStructure);
    GPIO_SetBits(GPIOC, GPIO_Pin_13);  // 初始熄灭（高电平灭）
}

#define LED_ON()   GPIO_ResetBits(GPIOC, GPIO_Pin_13)   // 低电平亮
#define LED_OFF()  GPIO_SetBits(GPIOC, GPIO_Pin_13)     // 高电平灭
#define LED_TOGGLE()                                           \
    do {                                                       \
        if (GPIO_ReadOutputDataBit(GPIOC, GPIO_Pin_13))        \
            GPIO_ResetBits(GPIOC, GPIO_Pin_13);                \
        else                                                   \
            GPIO_SetBits(GPIOC, GPIO_Pin_13);                  \
    } while(0)

/**
 * @brief 主函数
 *        初始化继电器GPIO和USART1串口，进入命令处理主循环
 *        通过RS-232接收PC上位机指令，控制继电器矩阵切换测量状态
 */
int main(void)
{
    uint32_t heartbeat_counter = 0;

    SystemInit();

    // 0. 看门狗：越早开启越好，初始化卡死也能复位
    IWDG_Init();

    // 1. 板载LED初始化
    LED_Init();
    LED_ON();  // 系统启动时点亮LED

    // 2. 初始化继电器GPIO（PA0-PA7, PB0推挽输出）
    Relay_GPIO_Init();

    // 3. 初始化USART1串口通讯（PA9-TX, PA10-RX, 115200-8N1）
    //    初始化完成后会自动发送启动横幅
    USART1_Comm_Init();

    // 4. 默认进入开路校准状态
    Relay_Set_OpenCalib();
    Delay_ms(10);

    LED_OFF(); // 初始化完成，熄灭LED
    USART1_SendLine("INFO:System ready. Default state: OPEN_CALIB");
    USART1_SendLine("INFO:Send 'HELP' for commands, 'STATUS' to check relays");

    // 5. 主循环：轮询串口命令 + 心跳包 + LED闪烁
    while (1)
    {
        IWDG_ReloadCounter();  // 喂狗：主循环正常就说明没卡死

        // --- 串口命令处理 ---
        if (USART1_CommandReady())
        {
            char cmd[USART_RX_BUF_SIZE];
            if (USART1_GetCommand(cmd, sizeof(cmd)))
            {
                LED_TOGGLE();  // 收到命令时LED翻转，肉眼可见通讯活动
                USART1_ProcessCommand(cmd);
            }
        }

        // --- 心跳包（约每5秒一次，方便确认串口通讯正常）---
        heartbeat_counter++;
        if (heartbeat_counter >= HEARTBEAT_INTERVAL)
        {
            heartbeat_counter = 0;
            USART1_SendLine("HEARTBEAT:system alive");
            LED_TOGGLE();  // 心跳LED翻转
        }

        // ==================================================
        // 此处可以添加其他后台任务：
        //   - ADC数据采集
        //   - 定时测量序列
        //   - 状态指示灯控制
        // ==================================================
    }
}
