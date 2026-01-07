import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def check_dependencies():
    """检查和安装依赖"""
    try:
        # 导入必要的库
        import telegram
        import requests
        import notion_client
        import bs4
        print("所有依赖已正确安装。")
        return True
    except ImportError as e:
        print(f"缺少依赖: {e}")
        choice = input("是否尝试安装缺少的依赖? (y/n): ")
        if choice.lower() == 'y':
            import subprocess
            print("安装依赖中...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            return True
        else:
            print("未安装依赖，程序无法运行。")
            return False

def check_environment():
    """检查环境变量设置"""
    load_dotenv()
    
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'NOTION_API_TOKEN',
        'NOTION_DATABASE_ID',
        'DEEPSEEK_API_KEY',
        'TARGET_CHAT_ID'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"缺少必要的环境变量: {', '.join(missing_vars)}")
        print("请确保你已经设置了 .env 文件或环境变量。")
        return False
    
    print("所有必要的环境变量已设置。")
    return True

if __name__ == "__main__":
    print("正在检查依赖...")
    deps_ok = check_dependencies()
    
    if deps_ok:
        print("\n正在检查环境变量...")
        env_ok = check_environment()
        
        if env_ok:
            print("\n环境检查完成，一切正常！")
            print("你可以通过运行 'python bot.py' 启动机器人。")
        else:
            print("\n环境检查失败，请修复上述问题后重试。")
    else:
        print("\n依赖检查失败，请修复上述问题后重试。")
