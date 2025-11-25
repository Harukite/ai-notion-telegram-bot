# AI-Notion Telegram 内容管理机器人

这是一个功能强大的 Telegram 机器人，可以将网页链接处理为结构化内容，并保存到 Notion 数据库中，帮助用户有效整理和管理网络信息。
平时撸猫信息太多太杂，使用X的收藏夹 ，内容一多 就不好整理了，所以做了这么一个机器人工具，方便自己整理信息

#### 直接发送推特链接给机器人
<img width="795" height="760" alt="image" src="https://github.com/user-attachments/assets/11e25f39-5983-423d-a090-d65c9bafd1a2" />

#### 解析完毕之后就会在notion中显示
<img width="1775" height="79" alt="image" src="https://github.com/user-attachments/assets/1dde7192-a370-4d8c-a6f2-b2a6f701f1ef" />




## 主要功能

1. **网页内容提取与分析**
   - 从用户发送的 URL 中提取网页内容，适配各类网站格式
   - 使用 DeepSeek AI API 进行内容分析和提取
   - 智能提取标题、摘要、关键点、标签和相关链接
   - 多层级内容提取策略，确保稳定性和内容质量

2. **Notion 数据库集成**
   - 将处理后的内容保存到 Notion 数据库
   - 支持按标签筛选和搜索数据库内容
   - 可添加自定义标签和状态（如"已完成"、"进行中"等）
   - 支持删除数据库条目

3. **Telegram 界面交互**
   - 输入框左侧的命令菜单按钮（汉堡菜单）
   - 丰富的命令和菜单操作
   - 标签筛选和搜索功能
   - 查看最近添加的条目
   - 内容预览和管理

4. **打卡系统**
   - 支持为重要内容设置提醒
   - 标记今日是否已打卡
   - 统计打卡次数

## 技术架构

- **Python 3.9+**: 主要开发语言
- **python-telegram-bot**: Telegram 机器人框架
- **BeautifulSoup**: 网页内容解析
- **requests**: HTTP 请求和 API 交互
- **DeepSeek API**: 内容分析与提取
- **Notion API**: 数据库交互与管理

## 文件结构

```
ai-notion/
├── bot.py               # 主机器人应用
├── config.py            # 配置和环境变量
├── content_processor.py # 内容处理与 AI 分析
├── notion_manager.py    # Notion 数据库管理
├── twitter_api.py       # Twitter API 交互
├── USER_GUIDE.md        # 用户指南
├── requirements.txt     # 依赖项
└── install_dependencies.sh # 环境设置脚本
```

## 安装与配置

1. 克隆此仓库：
```bash
git clone <repository-url>
cd ai-notion
```

2. 安装依赖：
```bash
# 使用自动安装脚本
./install_dependencies.sh

# 或手动安装
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. 配置环境变量（创建 `.env` 文件）：
```
# 必需配置
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_notion_database_id
DEEPSEEK_API_KEY=your_deepseek_api_key

# Twitter API配置 (可选)
# 当网页抓取失败时可使用官方API获取推文
TWITTER_API_KEY=your_twitter_api_key_here
TWITTER_API_SECRET=your_twitter_api_secret_here
TWITTER_ACCESS_TOKEN=your_twitter_access_token_here
TWITTER_ACCESS_SECRET=your_twitter_access_secret_here
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here
USE_TWITTER_API=false  # 设为true启用Twitter API
```

## 使用方法

1. 启动机器人：
```bash
python bot.py
```

2. 在 Telegram 中使用:
   - 点击输入框左侧的菜单按钮查看所有命令
   - `/start`: 启动机器人并获取帮助
   - `/menu`: 显示主菜单
   - `/help`: 显示帮助信息
   - 发送任何 URL: 提取内容并保存到 Notion
   - `/tags`: 显示所有可用标签
   - `/search`: 搜索内容
   - `/recent`: 显示最近添加的条目
   - `/checkin`: 标记今日是否打卡
   - `/checkcount`: 查看打卡次数

## 高级特性

- **命令菜单按钮**: 通过Telegram原生菜单按钮（输入框左侧）快速访问所有命令
- **鲁棒的网页内容提取**: 多种提取策略确保从各类网站获取内容
- **Twitter/X 多层级获取机制**:
  - Twitter API (官方API获取，需配置API密钥)
  - 网页抓取 (从Twitter/X网站直接抓取内容)
  - Nitter实例 (当直接抓取失败时使用Nitter镜像)
- **智能文本分析**: 使用 DeepSeek AI 提取关键信息
- **非JSON响应处理**: 高级正则表达式处理非标准 AI 响应格式
- **用户友好的错误处理**: 完善的错误处理和反馈机制

## 注意事项

- 确保已创建适当的 Notion 数据库，包含所需的属性字段
- 保持 `.env` 文件的安全，不要将其提交到版本控制系统
- 由于网站结构各异，某些网页的内容提取效果可能会有差异
- 更多详情请参考 USER_GUIDE.md 文件
