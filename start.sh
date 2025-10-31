#!/bin/bash

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 运行环境检查
echo "检查环境..."
python check_environment.py
python check_twitter_api.py

# 检查上一命令的退出状态
if [ $? -ne 0 ]; then
    echo "环境检查失败，请修复问题后重试。"
    exit 1
fi

# 启动机器人
echo "启动 Telegram 机器人..."
python bot.py
