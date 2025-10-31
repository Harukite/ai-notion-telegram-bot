#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Twitter API 依赖安装脚本 ===${NC}"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3 命令${NC}"
    echo "请确保已安装Python 3.6或更高版本"
    exit 1
fi

# 检查是否已安装tweepy
if python3 -c "import tweepy" &> /dev/null; then
    echo -e "${GREEN}✅ tweepy库已安装${NC}"
    
    # 获取tweepy版本
    TWEEPY_VERSION=$(python3 -c "import tweepy; print(tweepy.__version__)")
    echo -e "${GREEN}当前安装的tweepy版本: $TWEEPY_VERSION${NC}"
    
    # 检查版本是否符合要求 (>=4.14.0)
    if python3 -c "from packaging import version; import tweepy; exit(0) if version.parse(tweepy.__version__) >= version.parse('4.14.0') else exit(1)" &> /dev/null; then
        echo -e "${GREEN}✅ tweepy版本满足要求${NC}"
    else
        echo -e "${YELLOW}⚠️  tweepy版本过低，推荐4.14.0或更高版本${NC}"
        echo -e "${YELLOW}是否升级tweepy? (y/n)${NC}"
        read -r answer
        if [ "$answer" != "${answer#[Yy]}" ]; then
            echo "正在升级tweepy..."
            pip install --upgrade tweepy>=4.14.0
        else
            echo "跳过tweepy升级，部分功能可能受限"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  未安装tweepy库，这是使用Twitter API的必要依赖${NC}"
    echo -e "${YELLOW}是否安装tweepy? (y/n)${NC}"
    read -r answer
    if [ "$answer" != "${answer#[Yy]}" ]; then
        echo "正在安装tweepy..."
        pip install tweepy>=4.14.0
        
        # 检查安装结果
        if python3 -c "import tweepy" &> /dev/null; then
            echo -e "${GREEN}✅ tweepy库安装成功${NC}"
        else
            echo -e "${RED}❌ tweepy安装失败，请手动运行: pip install tweepy>=4.14.0${NC}"
            exit 1
        fi
    else
        echo "跳过tweepy安装，将无法使用Twitter API功能"
    fi
fi

echo -e "${YELLOW}\n=== Twitter API 配置检查 ===${NC}"
python3 check_twitter_api.py

echo -e "${GREEN}\n完成!${NC}"
