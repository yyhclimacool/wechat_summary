from wxauto import WeChat
from loguru import logger
from openai import OpenAI
import time
import datetime
import os

# 配置日志记录
logger.remove()  # 移除默认的处理器
logger.add(
    "logs/wx_summary_{time:YYYY-MM-DD}.log",  # 日志文件路径，按日期分割
    rotation="00:00",  # 每天零点创建新文件
    encoding="utf-8",
    enqueue=True,  # 异步写入
    format="{message}",  # 日志格式
    level="INFO",  # 记录的最低日志级别
)

def parse_message_time(msg_content):
    """解析系统消息时间"""
    try:
        if "昨天" in msg_content:
            time_str = msg_content[-5:]  # 获取HH:MM
            base_date = datetime.datetime.now() - datetime.timedelta(days=1)
            msg_datetime = datetime.datetime.combine(
                base_date.date(),
                datetime.datetime.strptime(time_str, '%H:%M').time()
            )
        else:
            time_str = msg_content[-5:]  # 获取HH:MM
            base_date = datetime.datetime.now()
            msg_datetime = datetime.datetime.combine(
                base_date.date(),
                datetime.datetime.strptime(time_str, '%H:%M').time()
            )
            
        return msg_datetime
        
    except Exception as e:
        logger.debug(f"时间解析错误: {e}, 消息内容: {msg_content}")
        return None

def get_wechat_messages(group_name, hours=None, ai_config=None, prompt=None):
    wx = WeChat()
    wx.ChatWith(group_name)

    if hours is None:
        start_time = datetime.datetime.now() - datetime.timedelta(hours=1)
    else:
        # 支持小数点形式的小时数
        start_time = datetime.datetime.now() - datetime.timedelta(hours=float(hours))
    
    logger.info(f"开始获取 {start_time} 之后的消息")
    print(f"开始获取 {start_time} 之后的消息")
    
    all_messages = []
    temp_messages = []
    processed_msgs = set()
    continue_loading = True
    load_count = 0
    max_load_attempts = 50

    current_msgs = wx.GetAllMessage()
    if current_msgs:
        for msg in reversed(current_msgs):
            msg_id = f"{msg.content}_{msg.sender}_{msg.type}"
            if msg_id in processed_msgs:
                continue
                
            processed_msgs.add(msg_id)
            
            if msg.type == 'time':
                msg_time = parse_message_time(msg.content)
                if msg_time and msg_time < start_time:
                    continue_loading = False
                    break
            
            if msg.type == 'sys':
                temp_messages.append(('sys', msg.content))
                all_messages.append(msg.content)
            elif msg.type == 'friend':
                temp_messages.append(('friend', msg.sender, msg.content))
                all_messages.append(f'{msg.sender}: {msg.content}')
            elif msg.type == 'self':
                if not msg.content.startswith("### 群聊精华总结"):
                    temp_messages.append(('self', msg.sender, msg.content))
                    all_messages.append(f'{msg.sender}: {msg.content}')
            elif msg.type == 'time':
                temp_messages.append(('time', msg.time))
            elif msg.type == 'recall':
                temp_messages.append(('recall', msg.content))
                all_messages.append(f'撤回消息: {msg.content}')

    while continue_loading and load_count < max_load_attempts:
        wx.LoadMoreMessage()
        time.sleep(2)
        load_count += 1
        
        current_msgs = wx.GetAllMessage()
        if not current_msgs:
            break
            
        for msg in reversed(current_msgs):
            msg_id = f"{msg.content}_{msg.sender}_{msg.type}"
            if msg_id in processed_msgs:
                continue
                
            processed_msgs.add(msg_id)
            
            if msg.type == 'sys':
                msg_time = parse_message_time(msg.content)
                if msg_time and msg_time < start_time:
                    continue_loading = False
                    break
            
            if msg.type == 'sys':
                temp_messages.append(('sys', msg.content))
                all_messages.append(msg.content)
            elif msg.type == 'friend':
                temp_messages.append(('friend', msg.sender, msg.content))
                all_messages.append(f'{msg.sender}: {msg.content}')
            elif msg.type == 'self':
                if not msg.content.startswith("### 群聊精华总结"):
                    temp_messages.append(('self', msg.sender, msg.content))
                    all_messages.append(f'{msg.sender}: {msg.content}')
            elif msg.type == 'time':
                temp_messages.append(('time', msg.time))
            elif msg.type == 'recall':
                temp_messages.append(('recall', msg.content))
                all_messages.append(f'撤回消息: {msg.content}')

    logger.info(f"共加载 {len(processed_msgs)} 条消息")
    print(f"共加载 {len(processed_msgs)} 条消息")
    print(f"起始时间为{msg_time}")
    
    all_messages.reverse()
    temp_messages.reverse()
    
    logger.info(f"【系统消息】{msg_time}")
    for msg in temp_messages:
        if msg[0] == 'sys':
            logger.info(f'【系统消息】{msg[1]}')
        elif msg[0] == 'friend':
            logger.info(f'{msg[1].rjust(20)}：{msg[2]}')
        elif msg[0] == 'self':
            logger.info(f'{msg[1].ljust(20)}：{msg[2]}')
        elif msg[0] == 'time':
            logger.info(f'\n【时间消息】{msg[1]}')
        elif msg[0] == 'recall':
            logger.info(f'【撤回消息】{msg[1]}')
            
    if ai_config and all_messages:
        client = OpenAI(
            api_key=ai_config['api_key'],
            base_url=ai_config['base_url']
        )
    
        messages_text = "\n".join(all_messages)
        try:
            completion = client.chat.completions.create(
                model=ai_config.get('model', 'qwen-plus'),
                messages=[
                    {
                        'role': 'system',
                        'content': prompt or '''你是一个专业的聊天记录总结员，请根据提供的微信群聊天记录生成一个简明的群聊精华总结，重点包括以下内容： 
                        1. 重要提醒：提取群聊中提到的任何提醒、禁止事项或重要信息。 
                        2. 今日热门话题：总结群聊中讨论过的主要话题，包含讨论时间、内容摘要、参与者以及关键建议或观点。 
                        3. 点评：对每个热门话题提供简短的点评，突出群聊中的实用建议或存在的问题。 
                        4. 待跟进事项：列出群聊中提到的待办事项或需要跟进的事项。 
                        5. 其他讨论话题：简要总结其他讨论内容。 
                        6. 结语：对整体讨论的总结，提到群友间的合作和技术交流。 
                        请确保精华总结简明扼要，突出重点，格式清晰易读。以下是微信群聊天记录：
                        '''
                    },
                    {
                        'role': 'user',
                        'content': messages_text
                    }
                ]
            )
            summary = completion.choices[0].message.content
            logger.info("\n=== 消息总结 ===\n" + summary)
            return summary
        except Exception as e:
            logger.error(f"消息总结失败: {e}")
            raise
    else:
        logger.info("未获取到任何消息或未提供AI配置")
        return None

def save_summary(group_name, summary, timestamp=None):
    """保存群聊总结到文件"""
    if timestamp is None:
        timestamp = datetime.datetime.now()
    
    # 确保目录名称合法
    safe_group_name = "".join(c for c in group_name if c.isalnum() or c in (' ', '-', '_'))
    
    summary_dir = "summary"
    if not os.path.exists(summary_dir):
        os.makedirs(summary_dir)
    
    filename = f"{summary_dir}/{safe_group_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}.txt"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"群聊：{group_name}\n")
            f.write(f"时间：{timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*50 + "\n")
            f.write(summary)
        logger.info(f"总结已保存到文件：{filename}")
        return filename
    except Exception as e:
        logger.error(f"保存总结失败：{str(e)}")
        return None

def send_summary(group_name, summary, max_retries=3):
    """发送群聊总结，支持重试机制"""
    if not summary:
        logger.error("没有要发送的总结内容")
        return False
    
    wx = WeChat()
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 确保成功切换到目标群聊
            if not wx.ChatWith(group_name):
                logger.error(f"未找到群聊：{group_name}")
                time.sleep(2)
                retry_count += 1
                continue
            
            # 分段发送长消息
            max_length = 2000  # 微信单条消息最大长度限制
            message = summary
            
            # 如果消息长度超过限制，分段发送
            if len(message) > max_length:
                parts = [message[i:i+max_length] for i in range(0, len(message), max_length)]
                for part in parts:
                    wx.SendMsg(part)
                    time.sleep(1)  # 添加发送间隔
            else:
                wx.SendMsg(message)
            
            logger.info("总结发送成功")
            return True
            
        except Exception as e:
            logger.error(f"发送失败 (尝试 {retry_count + 1}/{max_retries}): {str(e)}")
            time.sleep(2)
            retry_count += 1
    
    logger.error(f"发送总结失败，已达到最大重试次数 ({max_retries})")
    return False


if __name__ == "__main__":
    group_name = "VictorAI交流群"
    
    try:
        summary = get_wechat_messages(group_name, 1)
        if summary:
            saved_file = save_summary(group_name, summary)
            if saved_file:
                logger.info(f"总结已保存到：{saved_file}")
            
            if send_summary(group_name, summary):
                logger.info("总结已成功发送到群聊")
            else:
                logger.error("发送总结失败")
        else:
            logger.error("生成总结失败")
            
    except Exception as e:
        logger.error(f"程序执行出错：{str(e)}")

