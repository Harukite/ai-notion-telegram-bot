"""
Twitter API 环境检测工具
检查是否已安装tweepy库以及Twitter API配置是否完整
"""

import importlib
import logging
import os
import sys
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def check_tweepy_installed():
    """检查是否已安装tweepy库"""
    try:
        importlib.import_module('tweepy')
        logger.info("✅ tweepy库已安装")
        return True
    except ImportError:
        logger.warning("❌ tweepy库未安装，请运行 pip install tweepy 安装")
        return False

def check_twitter_config():
    """检查Twitter API配置是否完整"""
    # 加载环境变量
    load_dotenv()
    
    # 检查是否启用Twitter API
    use_twitter_api = os.getenv('USE_TWITTER_API', 'false').lower() == 'true'
    
    if not use_twitter_api:
        logger.warning("❌ Twitter API未启用，在.env文件中设置USE_TWITTER_API=true可启用")
        return False
    
    # 检查必要的API密钥是否存在
    required_keys = [
        'TWITTER_API_KEY', 
        'TWITTER_API_SECRET', 
        'TWITTER_BEARER_TOKEN'
    ]
    
    # 可选但推荐配置的密钥
    optional_keys = [
        'TWITTER_ACCESS_TOKEN', 
        'TWITTER_ACCESS_SECRET'
    ]
    
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    missing_optional = [key for key in optional_keys if not os.getenv(key)]
    
    if missing_keys:
        logger.warning(f"❌ 缺少必要的Twitter API配置: {', '.join(missing_keys)}")
        return False
    
    if missing_optional:
        logger.warning(f"⚠️ 缺少可选的Twitter API配置: {', '.join(missing_optional)}")
        logger.warning("⚠️ 某些API功能可能受限")
    
    logger.info("✅ Twitter API配置完整")
    return True

def main():
    """主函数"""
    print("\n=== Twitter API 环境检测 ===\n")
    
    tweepy_installed = check_tweepy_installed()
    config_complete = check_twitter_config()
    
    print("\n=== 检测结果汇总 ===")
    if tweepy_installed and config_complete:
        print("✅ Twitter API环境配置完成，可以正常使用")
    elif tweepy_installed:
        print("⚠️ tweepy库已安装，但API配置不完整")
        print("请在.env文件中正确配置Twitter API密钥并设置USE_TWITTER_API=true")
    elif config_complete:
        print("⚠️ API配置完整，但缺少tweepy库")
        print("请运行 pip install tweepy 安装所需库")
    else:
        print("❌ Twitter API环境配置不完整，无法使用")
        print("1. 请安装tweepy库: pip install tweepy")
        print("2. 在.env文件中配置正确的API密钥")
        print("3. 设置USE_TWITTER_API=true启用Twitter API")
    
    print("\n如不需要使用Twitter API，可忽略上述警告。")
    print("当设置USE_TWITTER_API=false时，系统将只使用网页抓取方式获取推文内容。")

if __name__ == "__main__":
    main()
