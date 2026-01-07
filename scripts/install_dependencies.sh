#!/bin/bash

echo "安装Notion-AI Bot依赖项..."
pip install -r requirements.txt

# 检查tweepy是否安装成功
if pip show tweepy &>/dev/null; then
    echo "✅ Twitter API (tweepy) 已成功安装"
else
    echo "⚠️ Twitter API (tweepy) 安装失败，尝试单独安装"
    pip install tweepy
fi

echo "安装完成。请确保.env文件中配置了所有必要的环境变量。"
echo "启动机器人: ./start.sh"
