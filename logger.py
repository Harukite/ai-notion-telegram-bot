import logging

def setup_logger():
    """配置日志"""
    # 创建日志记录器
    logger = logging.getLogger('ai_notion_bot')
    logger.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建文件处理器
    file_handler = logging.FileHandler('bot.log')
    file_handler.setLevel(logging.INFO)
    
    # 创建格式器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # 添加处理器到记录器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

# 为其他模块提供日志记录器
logger = setup_logger()
