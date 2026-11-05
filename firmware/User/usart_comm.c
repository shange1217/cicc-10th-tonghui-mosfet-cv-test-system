#include "usart_comm.h"
#include "relay_control.h"
#include <string.h>
#include <stdio.h>

//==================== 全局变量 ====================
uint8_t usart1_rx_buf[USART_RX_BUF_SIZE];   // 接收缓冲区
volatile uint8_t usart1_rx_index = 0;                 // 接收缓冲区写入索引
static volatile uint8_t cmd_ready = 0;                // 命令就绪标志
static char cmd_buffer[USART_RX_BUF_SIZE];   // 完整命令暂存区

// 当前系统状态
static System_State current_state = STATE_OPEN_CALIB;

//==================== USART1 初始化 ====================
/**
 * @brief USART1初始化：PA9(TX)推挽复用输出，PA10(RX)浮空输入
 *        波特率115200，8数据位，1停止位，无校验
 *        使能接收中断(RXNE)
 * @note  硬件连接：PA9→MAX232 T1IN, PA10→MAX232 R1OUT
 *        MAX232 T1OUT→PC RX(DB9-2), MAX232 R1IN→PC TX(DB9-3)
 */
void USART1_Comm_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStructure;
    USART_InitTypeDef USART_InitStructure;
    NVIC_InitTypeDef NVIC_InitStructure;

    // 1. 使能USART1和GPIOA时钟
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1 | RCC_APB2Periph_GPIOA, ENABLE);

    // 2. 配置PA9(TX)为复用推挽输出
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_9;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOA, &GPIO_InitStructure);

    // 3. 配置PA10(RX)为浮空输入
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_10;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN_FLOATING;
    GPIO_Init(GPIOA, &GPIO_InitStructure);

    // 4. 配置USART1: 115200-8-N-1
    //    BaudRate = Fck / (16 * USARTDIV) → USARTDIV = 72MHz / (16 * 115200) = 39.0625
    //    DIV_Mantissa = 39, DIV_Fraction = 0.0625 * 16 = 1
    USART_InitStructure.USART_BaudRate = USART_BAUDRATE;
    USART_InitStructure.USART_WordLength = USART_WordLength_8b;
    USART_InitStructure.USART_StopBits = USART_StopBits_1;
    USART_InitStructure.USART_Parity = USART_Parity_No;
    USART_InitStructure.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    USART_InitStructure.USART_Mode = USART_Mode_Rx | USART_Mode_Tx;
    USART_Init(USART1, &USART_InitStructure);

    // 5. 使能USART1接收中断（RXNE）
    USART_ITConfig(USART1, USART_IT_RXNE, ENABLE);

    // 6. 配置USART1中断优先级
    NVIC_InitStructure.NVIC_IRQChannel = USART1_IRQn;
    NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 1;
    NVIC_InitStructure.NVIC_IRQChannelSubPriority = 0;
    NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&NVIC_InitStructure);

    // 7. 使能USART1
    USART_Cmd(USART1, ENABLE);

    // 8. 初始化完成提示
    USART1_SendLine("\r\n====================================");
    USART1_SendLine("  Relay Matrix Control System v1.0");
    USART1_SendLine("  STM32F103 + 10-Channel Relay");
    USART1_SendLine("  RS-232 @ 115200-8N1");
    USART1_SendLine("  Type 'HELP' for command list");
    USART1_SendLine("====================================\r\n");
}

//==================== 基本发送函数 ====================
/**
 * @brief 发送单个字符（阻塞式）
 */
void USART1_SendChar(uint8_t ch)
{
    USART_SendData(USART1, (uint16_t)ch);
    while (USART_GetFlagStatus(USART1, USART_FLAG_TC) == RESET);
}

/**
 * @brief 发送字符串
 */
void USART1_SendString(const char* str)
{
    while (*str)
    {
        USART1_SendChar((uint8_t)*str);
        str++;
    }
}

/**
 * @brief 发送字符串并自动追加\r\n换行
 */
void USART1_SendLine(const char* str)
{
    USART1_SendString(str);
    USART1_SendChar('\r');
    USART1_SendChar('\n');
}

//==================== 状态查询 ====================
/**
 * @brief 获取当前系统状态枚举
 */
System_State GetCurrentState(void)
{
    return current_state;
}

/**
 * @brief 获取当前继电器状态描述字符串
 */
const char* GetCurrentStateName(void)
{
    switch (current_state)
    {
        case STATE_OPEN_CALIB:  return "OPEN_CALIB";
        case STATE_SHORT_CALIB: return "SHORT_CALIB";
        case STATE_CISS:        return "CISS";
        case STATE_COSS:        return "COSS";
        case STATE_CRSS:        return "CRSS";
        case STATE_RG_OPEN:     return "RG_OPEN";
        case STATE_RG_SHORT:    return "RG_SHORT";
        case STATE_CUSTOM:      return "CUSTOM";
        default:                return "UNKNOWN";
    }
}

//==================== 继电器状态查询 ====================
/**
 * @brief 读取单个继电器状态并发送
 */
static void SendRelayStatus(void)
{
    char buf[96];
    uint8_t k1  = GPIO_ReadOutputDataBit(RELAY_K1_PORT, RELAY_K1_PIN) ? 1 : 0;
    uint8_t k2  = GPIO_ReadOutputDataBit(RELAY_K2_PORT, RELAY_K2_PIN) ? 1 : 0;
    uint8_t k3  = GPIO_ReadOutputDataBit(RELAY_K3_PORT, RELAY_K3_PIN) ? 1 : 0;
    uint8_t k4  = GPIO_ReadOutputDataBit(RELAY_K4_PORT, RELAY_K4_PIN) ? 1 : 0;
    uint8_t k5  = GPIO_ReadOutputDataBit(RELAY_K5_PORT, RELAY_K5_PIN) ? 1 : 0;
    uint8_t k6  = GPIO_ReadOutputDataBit(RELAY_K6_PORT, RELAY_K6_PIN) ? 1 : 0;
    uint8_t k7  = GPIO_ReadOutputDataBit(RELAY_K7_PORT, RELAY_K7_PIN) ? 1 : 0;
    uint8_t k8  = GPIO_ReadOutputDataBit(RELAY_K8_PORT, RELAY_K8_PIN) ? 1 : 0;
    uint8_t k9  = GPIO_ReadOutputDataBit(RELAY_K9_PORT, RELAY_K9_PIN) ? 1 : 0;
    uint8_t k10 = GPIO_ReadOutputDataBit(RELAY_K10_PORT, RELAY_K10_PIN) ? 1 : 0;

    snprintf(buf, sizeof(buf), "STATUS:%s K1=%d K2=%d K3=%d K4=%d K5=%d K6=%d K7=%d K8=%d K9=%d K10=%d",
            GetCurrentStateName(), k1, k2, k3, k4, k5, k6, k7, k8, k9, k10);
    USART1_SendLine(buf);
}

//==================== 命令解析与执行 ====================
/**
 * @brief 去除字符串首尾空白字符
 */
static char* trim(char* str)
{
    char* end;
    // 去除前导空白
    while (*str == ' ' || *str == '\t' || *str == '\r' || *str == '\n')
        str++;
    if (*str == 0)
        return str;
    // 去除尾部空白
    end = str + strlen(str) - 1;
    while (end > str && (*end == ' ' || *end == '\t' || *end == '\r' || *end == '\n'))
        end--;
    *(end + 1) = '\0';
    return str;
}

/**
 * @brief 字符串转大写
 */
static void str_toupper(char* str)
{
    while (*str)
    {
        if (*str >= 'a' && *str <= 'z')
            *str -= 32;
        str++;
    }
}

/**
 * @brief 处理接收到的命令
 * @param cmd 接收到的ASCII命令字符串
 */
void USART1_ProcessCommand(const char* cmd_raw)
{
    char cmd[USART_RX_BUF_SIZE];
    char response[80];

    // 复制并清理命令
    strncpy(cmd, cmd_raw, USART_RX_BUF_SIZE - 1);
    cmd[USART_RX_BUF_SIZE - 1] = '\0';
    char* cmd_trimmed = trim(cmd);
    str_toupper(cmd_trimmed);

    // 空命令直接返回
    if (strlen(cmd_trimmed) == 0)
        return;

    //========== 测量状态切换命令 ==========
    if (strcmp(cmd_trimmed, "OPEN") == 0)
    {
        Relay_Set_OpenCalib();
        current_state = STATE_OPEN_CALIB;
        Delay_ms(10);
        snprintf(response, sizeof(response), "OK:%s", GetCurrentStateName());
        USART1_SendLine(response);
        USART1_SendLine("INFO:All relays OFF (Open Calibration)");
    }
    else if (strcmp(cmd_trimmed, "SHORT") == 0)
    {
        Relay_Set_ShortCalib();
        current_state = STATE_SHORT_CALIB;
        Delay_ms(10);
        snprintf(response, sizeof(response), "OK:%s", GetCurrentStateName());
        USART1_SendLine(response);
        USART1_SendLine("INFO:K1 ON, others OFF (Short Calibration)");
    }
    else if (strcmp(cmd_trimmed, "CISS") == 0)
    {
        Relay_Set_CISS();
        current_state = STATE_CISS;
        Delay_ms(10);
        snprintf(response, sizeof(response), "OK:%s", GetCurrentStateName());
        USART1_SendLine(response);
        USART1_SendLine("INFO:CISS measurement mode");
    }
    else if (strcmp(cmd_trimmed, "COSS") == 0)
    {
        Relay_Set_COSS();
        current_state = STATE_COSS;
        Delay_ms(10);
        snprintf(response, sizeof(response), "OK:%s", GetCurrentStateName());
        USART1_SendLine(response);
        USART1_SendLine("INFO:COSS measurement mode");
    }
    else if (strcmp(cmd_trimmed, "CRSS") == 0)
    {
        Relay_Set_CRSS();
        current_state = STATE_CRSS;
        Delay_ms(10);
        snprintf(response, sizeof(response), "OK:%s", GetCurrentStateName());
        USART1_SendLine(response);
        USART1_SendLine("INFO:CRSS measurement mode");
    }
    else if (strcmp(cmd_trimmed, "RGOPEN") == 0)
    {
        Relay_Set_RG_Open();
        current_state = STATE_RG_OPEN;
        Delay_ms(10);
        snprintf(response, sizeof(response), "OK:%s", GetCurrentStateName());
        USART1_SendLine(response);
        USART1_SendLine("INFO:RG (Open) measurement mode");
    }
    else if (strcmp(cmd_trimmed, "RGSHORT") == 0)
    {
        Relay_Set_RG_Short();
        current_state = STATE_RG_SHORT;
        Delay_ms(10);
        snprintf(response, sizeof(response), "OK:%s", GetCurrentStateName());
        USART1_SendLine(response);
        USART1_SendLine("INFO:RG (Short) measurement mode");
    }

    //========== 全部控制命令 ==========
    else if (strcmp(cmd_trimmed, "ALL OFF") == 0 || strcmp(cmd_trimmed, "ALL=0") == 0)
    {
        Relay_Set_OpenCalib();
        current_state = STATE_OPEN_CALIB;
        Delay_ms(10);
        USART1_SendLine("OK:All relays OFF");
    }
    else if (strcmp(cmd_trimmed, "ALL ON") == 0 || strcmp(cmd_trimmed, "ALL=1") == 0)
    {
        // 全部吸合（注意：仅用于测试，正常测量不需要）
        Relay_SetSingle(RELAY_K1_PIN, RELAY_K1_PORT, RELAY_ON);
        Relay_SetSingle(RELAY_K2_PIN, RELAY_K2_PORT, RELAY_ON);
        Relay_SetSingle(RELAY_K3_PIN, RELAY_K3_PORT, RELAY_ON);
        Relay_SetSingle(RELAY_K4_PIN, RELAY_K4_PORT, RELAY_ON);
        Relay_SetSingle(RELAY_K5_PIN, RELAY_K5_PORT, RELAY_ON);
        Relay_SetSingle(RELAY_K6_PIN, RELAY_K6_PORT, RELAY_ON);
        Relay_SetSingle(RELAY_K7_PIN, RELAY_K7_PORT, RELAY_ON);
        Relay_SetSingle(RELAY_K8_PIN, RELAY_K8_PORT, RELAY_ON);
        Relay_SetSingle(RELAY_K9_PIN, RELAY_K9_PORT, RELAY_ON);
        Relay_SetSingle(RELAY_K10_PIN, RELAY_K10_PORT, RELAY_ON);
        current_state = STATE_CUSTOM;
        Delay_ms(10);
        USART1_SendLine("OK:All relays ON");
    }

    //========== 单继电器控制命令 (K10 ON/OFF) ==========
    else if ((cmd_trimmed[0] == 'K' || cmd_trimmed[0] == 'k') &&
             cmd_trimmed[1] == '1' && cmd_trimmed[2] == '0' &&
             cmd_trimmed[3] == ' ')
    {
        char* param = cmd_trimmed + 4;  // 跳过 "K10 "

        if (strcmp(param, "ON") == 0 || strcmp(param, "1") == 0)
        {
            Relay_SetSingle(RELAY_K10_PIN, RELAY_K10_PORT, RELAY_ON);
            current_state = STATE_CUSTOM;
            Delay_ms(5);
            USART1_SendLine("OK:K10 ON");
        }
        else if (strcmp(param, "OFF") == 0 || strcmp(param, "0") == 0)
        {
            Relay_SetSingle(RELAY_K10_PIN, RELAY_K10_PORT, RELAY_OFF);
            current_state = STATE_CUSTOM;
            Delay_ms(5);
            USART1_SendLine("OK:K10 OFF");
        }
        else
        {
            snprintf(response, sizeof(response), "ERR:Unknown parameter '%s' (use ON/OFF or 1/0)", param);
            USART1_SendLine(response);
        }
    }

    //========== 单继电器控制命令 (K1~K9 ON/OFF) ==========
    else if ((cmd_trimmed[0] == 'K' || cmd_trimmed[0] == 'k') &&
             cmd_trimmed[1] >= '1' && cmd_trimmed[1] <= '9' &&
             cmd_trimmed[2] == ' ')
    {
        uint8_t relay_num = cmd_trimmed[1] - '0';  // 1~9
        char* param = cmd_trimmed + 3;  // 跳过 "Kx "

        uint16_t pin;
        GPIO_TypeDef* port;

        // 根据继电器编号获取对应的引脚和端口
        switch (relay_num)
        {
            case 1: pin = RELAY_K1_PIN; port = RELAY_K1_PORT; break;
            case 2: pin = RELAY_K2_PIN; port = RELAY_K2_PORT; break;
            case 3: pin = RELAY_K3_PIN; port = RELAY_K3_PORT; break;
            case 4: pin = RELAY_K4_PIN; port = RELAY_K4_PORT; break;
            case 5: pin = RELAY_K5_PIN; port = RELAY_K5_PORT; break;
            case 6: pin = RELAY_K6_PIN; port = RELAY_K6_PORT; break;
            case 7: pin = RELAY_K7_PIN; port = RELAY_K7_PORT; break;
            case 8: pin = RELAY_K8_PIN; port = RELAY_K8_PORT; break;
            case 9: pin = RELAY_K9_PIN; port = RELAY_K9_PORT; break;
            default: return;
        }

        if (strcmp(param, "ON") == 0 || strcmp(param, "1") == 0)
        {
            Relay_SetSingle(pin, port, RELAY_ON);
            current_state = STATE_CUSTOM;
            Delay_ms(5);
            snprintf(response, sizeof(response), "OK:K%d ON", relay_num);
            USART1_SendLine(response);
        }
        else if (strcmp(param, "OFF") == 0 || strcmp(param, "0") == 0)
        {
            Relay_SetSingle(pin, port, RELAY_OFF);
            current_state = STATE_CUSTOM;
            Delay_ms(5);
            snprintf(response, sizeof(response), "OK:K%d OFF", relay_num);
            USART1_SendLine(response);
        }
        else
        {
            snprintf(response, sizeof(response), "ERR:Unknown parameter '%s' (use ON/OFF or 1/0)", param);
            USART1_SendLine(response);
        }
    }

    //========== 查询命令 ==========
    else if (strcmp(cmd_trimmed, "STATUS") == 0)
    {
        SendRelayStatus();
    }

    //========== 帮助命令 ==========
    else if (strcmp(cmd_trimmed, "HELP") == 0 || strcmp(cmd_trimmed, "?") == 0)
    {
        USART1_SendLine("========== Command List ==========");
        USART1_SendLine(" Measurement States:");
        USART1_SendLine("   OPEN      - Open calibration (all off)");
        USART1_SendLine("   SHORT     - Short calibration (K1 on)");
        USART1_SendLine("   CISS      - CISS measurement");
        USART1_SendLine("   COSS      - COSS measurement");
        USART1_SendLine("   CRSS      - CRSS measurement");
        USART1_SendLine("   RGOPEN    - RG (open) measurement");
        USART1_SendLine("   RGSHORT   - RG (short) measurement");
        USART1_SendLine(" Relay Control:");
        USART1_SendLine("   K1 ON     - Set K1 ON  (K1~K10)");
        USART1_SendLine("   K1 OFF    - Set K1 OFF (K1~K10)");
        USART1_SendLine("   ALL OFF   - All relays OFF");
        USART1_SendLine("   ALL ON    - All relays ON");
        USART1_SendLine(" System:");
        USART1_SendLine("   STATUS    - Show relay states");
        USART1_SendLine("   HELP / ?  - Show this help");
        USART1_SendLine("====================================");
    }

    //========== 未知命令 ==========
    else
    {
        snprintf(response, sizeof(response), "ERR:Unknown command '%s' (type HELP)", cmd_trimmed);
        USART1_SendLine(response);
    }
}

//==================== 接收中断服务函数（由stm32f10x_it.c调用） ====================
/**
 * @brief USART1接收中断处理
 * @note  此函数需要在USART1_IRQHandler中调用
 *        每收到一个字节存入缓冲区，遇到\r\n认为一条命令结束
 */
void USART1_RX_IRQHandler(void)
{
    uint8_t ch;

    // 读取接收到的字节（同时清除RXNE标志）
    if (USART_GetFlagStatus(USART1, USART_FLAG_RXNE) == SET)
    {
        ch = (uint8_t)USART_ReceiveData(USART1);

        // 忽略单独的回车符(0x0D)
        if (ch == '\r')
            return;

        // 换行符(0x0A)表示一条命令结束
        if (ch == '\n')
        {
            if (usart1_rx_index > 0)
            {
                usart1_rx_buf[usart1_rx_index] = '\0';  // 添加字符串结束符
                // 上一条命令还没被主循环取走时丢弃新命令，避免覆盖正在拷贝的缓冲区
                if (cmd_ready == 0)
                {
                    strncpy(cmd_buffer, (char*)usart1_rx_buf, USART_RX_BUF_SIZE - 1);
                    cmd_buffer[USART_RX_BUF_SIZE - 1] = '\0';
                    cmd_ready = 1;  // 设置命令就绪标志
                }
                usart1_rx_index = 0;  // 复位缓冲区索引
            }
        }
        else
        {
            // 普通字符存入缓冲区
            if (usart1_rx_index < USART_RX_BUF_SIZE - 1)
            {
                usart1_rx_buf[usart1_rx_index++] = ch;
            }
            else
            {
                // 缓冲区溢出，丢弃并复位
                usart1_rx_index = 0;
            }
        }
    }

    // 溢出错误处理：清除ORE标志
    if (USART_GetFlagStatus(USART1, USART_FLAG_ORE) == SET)
    {
        (void)USART_ReceiveData(USART1);  // 读取DR清除ORE
    }
}

/**
 * @brief 查询是否有新命令就绪
 * @return 1=有新命令待处理, 0=无
 */
uint8_t USART1_CommandReady(void)
{
    return cmd_ready;
}

/**
 * @brief 获取并清除就绪命令
 * @param buf 输出缓冲区
 * @param size 缓冲区大小
 * @return 1=成功获取命令, 0=无命令
 */
uint8_t USART1_GetCommand(char* buf, uint8_t size)
{
    if (cmd_ready == 0 || size == 0)
        return 0;

    strncpy(buf, cmd_buffer, size - 1);
    buf[size - 1] = '\0';
    cmd_ready = 0;
    return 1;
}
