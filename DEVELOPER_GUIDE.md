# AI-Notion Telegram 内容管理机器人开发文档

## 项目概述

AI-Notion Telegram 机器人是一个功能强大的内容管理助手，它可以将网页内容结构化并保存到 Notion 数据库中。主要用于信息收集、整理和管理。

## 技术架构

### 主要组件

1. **应用入口 (`app/main.py`)**
   - Telegram 机器人启动与命令注册
   - 会话控制与消息分发

2. **内容处理器 (`app/core/content_processor.py`)**
   - 网页内容提取
   - DeepSeek AI 分析与结构化
   - 文本清理和格式化

3. **Notion 服务 (`app/services/notion_service.py`)**
   - Notion API 交互
   - 数据库条目管理
   - 内容同步与更新

4. **Twitter 服务 (`app/services/twitter_service.py`)**
   - Twitter 内容获取
   - API 认证与错误处理

5. **配置管理 (`app/config.py`)**
   - 环境变量处理
   - API 密钥管理
   - 运行时配置

### 依赖项

```python
# 主要依赖
python-telegram-bot==20.4
requests==2.28.1
beautifulsoup4==4.11.1
notion-client==1.0.0
python-dotenv==0.21.0
tweepy==4.12.0
```

## 核心功能实现

### 1. Telegram 命令系统

在 `app/main.py` 中实现了以下命令处理器:

```python
# 命令处理器
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("menu", menu_command))
# ...其他命令处理器
```

命令菜单设置:

```python
async def setup_commands(application) -> None:
    commands = [
        BotCommand("start", "开始使用机器人"),
        BotCommand("help", "获取帮助信息"),
        BotCommand("menu", "显示主菜单"),
        BotCommand("search", "搜索内容"),
        BotCommand("tags", "查看所有标签"),
        BotCommand("recent", "查看最近内容"),
        BotCommand("status", "管理内容状态"),
        BotCommand("delete", "删除内容"),
        BotCommand("checkin", "每日打卡"),
        BotCommand("checkcount", "查看打卡统计"),
        BotCommand("version", "显示版本信息")
    ]
    await application.bot.set_my_commands(commands)
```

### 2. 内容提取与处理

`content_processor.py` 中的多级提取策略:

```python
def extract_webpage_content(url):
    # 基本网页提取
    html_content = fetch_html_content(url)
    if not html_content:
        return None
        
    # 针对不同网站的特殊处理
    if "twitter.com" in url or "x.com" in url:
        return extract_twitter_content(url, html_content)
    elif "youtube.com" in url:
        return extract_youtube_content(url, html_content)
    else:
        return extract_general_content(url, html_content)
```

### 3. DeepSeek AI 集成

```python
def analyze_with_deepseek(text, url):
    headers = {
        'Authorization': f'Bearer {config.DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    prompt = f"""分析以下内容并提取关键信息:
    URL: {url}
    
    内容:
    {text}
    
    请提取以下结构化信息:
    1. 标题
    2. 摘要 (100-150字)
    3. 关键点 (3-5个要点)
    4. 建议标签 (3-5个)
    5. 相关链接 (如有)
    
    以JSON格式返回。
    """
    
    # API调用和响应处理...
```

### 4. Notion 数据库交互

`app/services/notion_service.py` 中的核心函数:

```python
def save_to_notion(title, summary, key_points, tags, url):
    """将提取的内容保存到Notion数据库"""
    
    properties = {
        "标题": {"title": [{"text": {"content": title}}]},
        "摘要": {"rich_text": [{"text": {"content": summary}}]},
        "链接": {"url": url},
        "标签": {"multi_select": [{"name": tag} for tag in tags]},
        "状态": {"select": {"name": "未读"}},
        "添加日期": {"date": {"start": datetime.now().isoformat()}}
    }
    
    # 创建数据库条目...
```

### 5. 命令菜单实现

在 `app/main.py` 中通过 `post_init` 函数在应用启动时设置命令菜单:

```python
async def post_init(application: Application) -> None:
    """应用启动后的初始化任务"""
    await setup_commands(application)
    print("机器人命令菜单已设置")

def main() -> None:
    """启动机器人应用"""
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # 设置命令处理器...
    
    # 设置post_init函数
    application.post_init = post_init
    
    # 启动应用
    application.run_polling()
```

## 错误处理与日志记录

```python
# 全局错误处理
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理更新过程中发生的错误"""
    logger.error(f"更新 {update} 导致错误 {context.error}")
    
    # 向用户发送错误通知
    if update.effective_message:
        error_message = "处理请求时出现错误，请稍后再试。"
        await update.effective_message.reply_text(error_message)
        
    # 详细日志记录
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    logger.error(f"错误详情:\n{tb_string}")
```

## 部署指南

### 环境设置

1. 创建并激活虚拟环境:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. 安装依赖:
```bash
pip install -r requirements.txt
```

3. 配置环境变量 (`.env` 文件):
```
TELEGRAM_BOT_TOKEN=your_bot_token
NOTION_API_TOKEN=your_notion_token
NOTION_DATABASE_ID=your_database_id
DEEPSEEK_API_KEY=your_deepseek_key
TARGET_CHAT_ID=your_target_chat_id
# ...其他配置
```

可选配置:

```
TWITTER_API_KEY=your_twitter_api_key_here
TWITTER_API_SECRET=your_twitter_api_secret_here
TWITTER_ACCESS_TOKEN=your_twitter_access_token_here
TWITTER_ACCESS_SECRET=your_twitter_access_secret_here
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here
USE_TWITTER_API=false

SCRAPER_TECH_ENDPOINT=https://api.scraper.tech/tweet.php
SCRAPER_TECH_KEY=your_scraper_tech_key
RAPIDAPI_KEY=your_rapidapi_key
```

### 运行

```bash
python3 -m app.main
```

### 部署到服务器

1. 使用 systemd 服务 (Linux):
```
[Unit]
Description=AI-Notion Telegram Bot
After=network.target

[Service]
User=username
WorkingDirectory=/path/to/ai-notion
ExecStart=/path/to/ai-notion/venv/bin/python -m app.main
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

2. 使用 Docker:
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "app.main"]
```

## 测试

1. 单元测试:
```python
# test_content_processor.py
import unittest
from content_processor import extract_webpage_content

class TestContentProcessor(unittest.TestCase):
    def test_extract_general_content(self):
        # 测试一般网页内容提取
        url = "https://example.com/article"
        result = extract_webpage_content(url)
        self.assertIsNotNone(result)
        self.assertIn('title', result)
        self.assertIn('text', result)
```

2. 集成测试:
- 模拟 Telegram 更新
- 验证 Notion 数据库条目创建
- 测试错误情况和边缘案例

## 扩展与未来功能

1. **多语言支持**:
   - 添加语言选择命令
   - 实现本地化翻译系统

2. **高级内容分析**:
   - 情感分析
   - 主题分类
   - 关键词提取增强

3. **用户个性化**:
   - 自定义模板
   - 个人标签系统
   - 内容推荐

4. **调度与提醒**:
   - 定期内容汇总
   - 阅读提醒
   - 标签订阅

5. **性能优化**:
   - 异步内容处理
   - 缓存机制
   - 批量操作支持

## 故障排查

### 常见问题

1. **Telegram 命令无响应**:
   - 检查机器人令牌是否有效
   - 验证命令处理器是否正确注册
   - 检查 Telegram API 连接状态

2. **内容提取失败**:
   - 网站是否有反爬虫机制
   - 网页结构是否变更
   - 请求是否被限制或阻止

3. **Notion API 错误**:
   - 验证 API 密钥权限
   - 检查数据库结构是否兼容
   - 网络连接问题

4. **AI 分析异常**:
   - DeepSeek API 配额限制
   - 非标准响应格式处理
   - 输入文本过长或格式问题

## 维护与更新

1. **日常维护**:
   - 监控错误日志
   - 检查 API 限制和配额
   - 备份数据库结构

2. **版本更新流程**:
   - 功能测试
   - 用户反馈收集
   - 发布说明准备
   - 平滑升级策略

---

*此开发文档供内部参考，详细介绍了AI-Notion Telegram机器人的技术实现和维护指南。*
