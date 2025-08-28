import os
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 环境变量检查
required_vars = [
    'TELEGRAM_BOT_TOKEN',
    'NOTION_API_TOKEN',
    'NOTION_DATABASE_ID',
    'DEEPSEEK_API_KEY'
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"缺少必要的环境变量: {', '.join(missing_vars)}")

# 配置常量
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
NOTION_API_TOKEN = os.getenv('NOTION_API_TOKEN')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

# Twitter API 配置常量
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY', '')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET', '')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN', '')
TWITTER_ACCESS_SECRET = os.getenv('TWITTER_ACCESS_SECRET', '')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN', '')

# 是否启用 Twitter API
USE_TWITTER_API = os.getenv('USE_TWITTER_API', 'false').lower() == 'true'

# 检查是否有 Twitter API 相关配置（可选，非必需）
HAS_TWITTER_CONFIG = bool(TWITTER_API_KEY and TWITTER_API_SECRET and TWITTER_BEARER_TOKEN)

# 确认是否能够使用 Twitter API（同时满足配置有效和明确启用）
CAN_USE_TWITTER_API = USE_TWITTER_API and HAS_TWITTER_CONFIG

# DeepSeek API 配置常量
DEEPSEEK_API_TIMEOUT = int(os.getenv('DEEPSEEK_API_TIMEOUT', '60'))  # API请求超时时间，默认60秒
DEEPSEEK_API_MAX_RETRIES = int(os.getenv('DEEPSEEK_API_MAX_RETRIES', '3'))  # API请求最大重试次数，默认3次
DEEPSEEK_API_RETRY_DELAY = int(os.getenv('DEEPSEEK_API_RETRY_DELAY', '5'))  # API请求重试初始延迟时间，默认5秒

# 记录重要配置信息
logger = logging.getLogger(__name__)
logger.info("======== 系统配置信息 ========")
logger.info(f"DeepSeek API 超时设置: {DEEPSEEK_API_TIMEOUT}秒")
logger.info(f"DeepSeek API 最大重试次数: {DEEPSEEK_API_MAX_RETRIES}次")
logger.info(f"DeepSeek API 重试初始延迟: {DEEPSEEK_API_RETRY_DELAY}秒")
logger.info(f"Twitter API 启用状态: {'已启用' if CAN_USE_TWITTER_API else '未启用'}")
if not CAN_USE_TWITTER_API and USE_TWITTER_API:
    logger.warning("Twitter API 已启用但配置不完整，请检查API密钥设置")
logger.info("==============================")
