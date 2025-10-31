import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from config import TELEGRAM_BOT_TOKEN
from content_processor import ContentProcessor
from notion_manager import NotionManager

def escape_markdown(text):
    """转义 Telegram Markdown V1 特殊字符"""
    if not text:
        return ""
    # Telegram Markdown V1 需要转义 _ * [ ] ( ) ~ ` > # + - = | { } . !
    return re.sub(r'([_\*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 初始化处理器
content_processor = ContentProcessor()
notion_manager = NotionManager()

# 状态选项
STATUS_OPTIONS = ["未处理", "进行中", "已完成", "已放弃"]

# 今日是否打卡选项
CHECK_IN_OPTIONS = ["是", "否"]

# 是否提醒选项
REMINDER_OPTIONS = [True, False]

# 主菜单选项
MAIN_MENU_OPTIONS = [
    {"text": "📝 添加新内容", "callback": "menu_add_content"},
    {"text": "🏷️ 查看标签", "callback": "menu_tags"},
    {"text": "🔍 搜索内容", "callback": "menu_search"},
    {"text": "📊 最近添加", "callback": "menu_recent"},
    {"text": "✅ 打卡管理", "callback": "menu_checkin"},
    {"text": "⚙️ 设置", "callback": "menu_settings"},
    {"text": "❓ 帮助", "callback": "menu_help"}
]

# 帮助消息
HELP_MESSAGE = """
欢迎使用内容管理机器人！

*可用命令:*
/start - 开始使用机器人
/menu - 显示主菜单（推荐使用）
/mymenu - "我的菜单"快捷方式
/help - 显示帮助信息
/tags - 列出所有标签
/status - 更改条目状态
/reminder - 设置是否提醒
/checkin - 标记今日是否完成打卡
/checkcount - 查看打卡次数
/recent - 显示最近添加的条目
/search - 搜索条目

*基本使用:*
1. 使用 /menu 命令打开主菜单，选择需要的功能
2. 直接发送链接，机器人将自动处理并保存到Notion
3. 使用菜单中的"查看标签"筛选标签内容
4. 在标签不存在时，可以直接创建新标签

*提示:*
- 链接处理可能需要几秒钟时间
- 您可以随时添加新标签或删除条目
- 摘要内容将自动从链接中提取
- 主菜单提供所有功能的快捷入口
"""

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """显示主菜单"""
    # 创建主菜单按钮 - 使用ReplyKeyboardMarkup代替InlineKeyboardMarkup
    keyboard = []
    # 按两列排列菜单按钮
    row = []
    for i, option in enumerate(MAIN_MENU_OPTIONS):
        row.append(KeyboardButton(option["text"]))
        # 每两个选项为一行，或者到达最后一个选项
        if len(row) == 2 or i == len(MAIN_MENU_OPTIONS) - 1:
            keyboard.append(row)
            row = []
    
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,  # 自动调整大小
        one_time_keyboard=False,  # 保持显示，不会在用户按下后消失
        input_field_placeholder="选择一个选项或发送消息"  # 输入框占位符
    )
    
    await update.message.reply_text( # type: ignore
        "📋 *主菜单*\n\n"
        "请选择您需要的功能:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /start 命令"""
    user = update.effective_user
    await update.message.reply_text( # type: ignore
        f"你好，{user.first_name}！我是内容管理机器人。\n" # type: ignore
        f"发送任何链接，我将自动整理内容并保存到Notion。\n"
        f"使用 /menu 查看主菜单或 /help 查看更多帮助信息。"
    )
    
    # 显示主菜单
    await show_main_menu(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /help 命令"""
    await update.message.reply_text( # type: ignore
        HELP_MESSAGE,
        parse_mode='Markdown'
    )
    
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /menu 命令"""
    await show_main_menu(update, context)
    
async def my_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /mymenu 命令，"我的菜单"的快捷方式"""
    await show_main_menu(update, context)

async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理消息中的链接"""
    # 检测链接
    url_pattern = r'https?://\S+'
    message_text = update.message.text
    urls = re.findall(url_pattern, message_text)
    
    if not urls:
        await update.message.reply_text("请发送有效的URL链接。")
        return
    
    # 处理第一个检测到的链接
    url = urls[0]
    
    # 告知用户正在处理
    processing_message = await update.message.reply_text(
        f"正在处理链接: {url}\n这可能需要一点时间，请稍候..."
    )
    
    try:
        # 处理链接内容
        processed_data = content_processor.process_link(url)
        
        # 检查处理结果是否包含错误相关关键词或特殊错误标记
        has_error = False
        error_keywords = ["API请求超时", "处理超时", "连接失败", "处理失败", "无法获取"]
        
        # 检查标题、摘要和标签中是否包含错误关键词
        if any(keyword in processed_data.get('title', '') for keyword in error_keywords) or \
           any(keyword in processed_data.get('summary', '') for keyword in error_keywords) or \
           any(error_tag in processed_data.get('tags', []) for error_tag in ["API超时", "处理错误", "连接错误", "访问失败"]):
            has_error = True
        
        # 特别检查关键点中是否包含明确的错误信息
        key_points = processed_data.get('key_points', [])
        if key_points and any("错误" in point or "失败" in point or "API" in point for point in key_points):
            has_error = True
            
        if has_error:
            # 如果处理过程出现错误，不保存到Notion，直接显示错误信息
            error_summary = escape_markdown(processed_data.get('summary', '处理过程中出现错误'))
            error_message = (
                f"❌ 处理链接时遇到问题，内容未保存到Notion\n\n"
                f"*原因:* {error_summary}\n\n"
                f"请稍后再试，或尝试其他链接。"
            )
            await processing_message.edit_text(error_message, parse_mode='Markdown')
            return
        
        # 内容处理成功，先检查是否已存在相同链接
        existing = notion_manager.find_entry_by_link(processed_data.get('original_url'))
        if existing:
            title_existing = escape_markdown(existing.get('title') or '无标题')
            url_existing = processed_data.get('original_url')
            keyboard = [[InlineKeyboardButton("查看已存在的条目", callback_data=f"show_entry:{existing['id']}")]]
            await processing_message.edit_text(
                f"ℹ️ 该链接已存在，不重复添加。\n\n*标题:* {title_existing}\n*链接:* {url_existing}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return
        
        # 未重复，保存到Notion
        result = notion_manager.add_content_to_database(processed_data)
        
        if result["success"]:
            # 构建响应消息
            title = escape_markdown(processed_data['title'])
            tags = escape_markdown(', '.join(processed_data['tags']))
            source = escape_markdown(processed_data['source'])
            summary = escape_markdown(processed_data['summary'][:200])
            
            response = (
                f"✅ 内容已成功保存到Notion!\n\n"
                f"*标题:* {title}\n"
                f"*标签:* {tags}\n"
                f"*来源:* {source}\n\n"
                f"*摘要:*\n{summary}...\n"
            )
            
            # 创建内联键盘用于后续操作
            keyboard = [
                [InlineKeyboardButton("更改状态", callback_data=f"status:{result['page_id']}")],
                [InlineKeyboardButton("添加标签", callback_data=f"add_tag:{result['page_id']}")],
                [InlineKeyboardButton("删除", callback_data=f"delete:{result['page_id']}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # 更新或发送新消息
            await processing_message.edit_text(
                response,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            error_msg = escape_markdown(result.get('error', '未知错误'))
            await processing_message.edit_text(
                f"❌ 保存到Notion时出错: {error_msg}\n\n请稍后再试。"
            )
    
    except Exception as e:
        logger.error(f"处理链接时出错: {str(e)}")
        error_msg = escape_markdown(str(e))
        await processing_message.edit_text(
            f"❌ 处理链接时出错: {error_msg}\n\n请稍后再试。"
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理按钮回调查询"""
    query = update.callback_query
    await query.answer()
    
    # 解析回调数据
    data = query.data.split(":")
    action = data[0]
    page_id = data[1] if len(data) > 1 else None
    
    if action == "status" and page_id:
        # 显示状态选择菜单
        keyboard = [[InlineKeyboardButton(status, callback_data=f"set_status:{page_id}:{status}")] 
                    for status in STATUS_OPTIONS]
        keyboard.append([InlineKeyboardButton("取消", callback_data="cancel")])
        
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "set_status" and len(data) > 2:
        # 设置新状态
        status = data[2]
        result = notion_manager.update_entry_status(page_id, status)
        
        if result["success"]:
            # 恢复原始按钮
            keyboard = [
                [InlineKeyboardButton("更改状态", callback_data=f"status:{page_id}")],
                [InlineKeyboardButton("添加标签", callback_data=f"add_tag:{page_id}")],
                [InlineKeyboardButton("删除", callback_data=f"delete:{page_id}")]
            ]
            
            await query.edit_message_text(
                f"{query.message.text}\n\n*状态已更新为:* {status}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            error_msg = escape_markdown(result.get('error', '未知错误'))
            await query.edit_message_text(
                f"{query.message.text}\n\n❌ 更新状态失败: {error_msg}",
                parse_mode='Markdown'
            )
    
    elif action == "add_tag" and page_id:
        # 存储页面ID用于后续操作
        context.user_data["current_page_id"] = page_id
        
        await query.edit_message_text(
            f"{query.message.text}\n\n请输入要添加的标签名称:",
            parse_mode='Markdown'
        )
        
        # 设置期望响应标记
        context.user_data["expecting_tag"] = True
    
    elif action == "delete" and page_id:
        # 确认删除
        keyboard = [
            [InlineKeyboardButton("确认删除", callback_data=f"confirm_delete:{page_id}")],
            [InlineKeyboardButton("取消", callback_data="cancel")]
        ]
        
        await query.edit_message_text(
            f"{query.message.text}\n\n⚠️ 确定要删除此条目吗？此操作不可撤销。",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif action == "confirm_delete" and page_id:
        # 执行删除操作
        result = notion_manager.delete_entry(page_id)
        
        if result["success"]:
            # 若用户来自“最近添加”视图，则删除后返回该列表
            if context.user_data.get("last_view") == "recent":
                entries = notion_manager.get_entries_with_details(limit=5)
                if not entries:
                    await query.edit_message_text(
                        "*最近添加*\n\n目前没有任何条目。",
                        parse_mode='Markdown'
                    )
                else:
                    message_text = "*最近添加的条目:*\n\n"
                    keyboard = []
                    for entry in entries:
                        title = escape_markdown(entry["title"] or "无标题")
                        status = escape_markdown(entry["status"] or "未知状态")
                        entry_id_next = entry["id"]
                        summary = escape_markdown(entry["summary"] or "无摘要")
                        message_text += f"• *{title}* ({status})\n"
                        message_text += f"  {summary[:100]}...\n\n"
                        keyboard.append([InlineKeyboardButton(
                            f"{title[:20]}...",
                            callback_data=f"show_entry:{entry_id_next}"
                        )])
                    keyboard.append([InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")])
                    await query.edit_message_text(
                        message_text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
            else:
                await query.edit_message_text(
                    f"✅ 条目已成功删除!",
                    parse_mode='Markdown'
                )
        else:
            error_msg = escape_markdown(result.get('error', '未知错误'))
            await query.edit_message_text(
                f"❌ 删除条目失败: {error_msg}",
                parse_mode='Markdown'
            )
            
    elif action == "checkin_status" and page_id:
        # 显示打卡状态选择菜单
        keyboard = [[InlineKeyboardButton(status, callback_data=f"set_checkin:{page_id}:{status}")] 
                    for status in CHECK_IN_OPTIONS]
        keyboard.append([InlineKeyboardButton("取消", callback_data=f"show_entry:{page_id}")])
        
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "set_checkin" and page_id:
        # 设置打卡状态
        status_value = data[2] if len(data) > 2 else "否"
        is_checked_in = status_value == "是"
        
        # 更新打卡状态
        result = notion_manager.update_check_in_status(page_id, status_value)
        
        if result["success"] and is_checked_in:
            # 如果标记为已打卡，增加计数
            count_result = notion_manager.increment_check_in_count(page_id)
            
            if count_result["success"]:
                await query.edit_message_text(
                    f"{query.message.text}\n\n*今日打卡状态已更新为:* {status_value}\n*打卡次数已增加!*",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回", callback_data=f"show_entry:{page_id}")]]),
                    parse_mode='Markdown'
                )
            else:
                error_msg = escape_markdown(count_result.get('error', '未知错误'))
                await query.edit_message_text(
                    f"{query.message.text}\n\n*今日打卡状态已更新为:* {status_value}\n❌ 但打卡次数增加失败: {error_msg}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回", callback_data=f"show_entry:{page_id}")]]),
                    parse_mode='Markdown'
                )
        elif result["success"]:
            await query.edit_message_text(
                f"{query.message.text}\n\n*今日打卡状态已更新为:* {status_value}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回", callback_data=f"show_entry:{page_id}")]]),
                parse_mode='Markdown'
            )
        else:
            error_msg = escape_markdown(result.get('error', '未知错误'))
            await query.edit_message_text(
                f"{query.message.text}\n\n❌ 更新打卡状态失败: {error_msg}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回", callback_data=f"show_entry:{page_id}")]]),
                parse_mode='Markdown'
            )
            
    elif action == "set_reminder" and page_id:
        # 显示提醒状态选择菜单
        keyboard = [
            [InlineKeyboardButton("开启提醒", callback_data=f"update_reminder:{page_id}:True")],
            [InlineKeyboardButton("关闭提醒", callback_data=f"update_reminder:{page_id}:False")],
            [InlineKeyboardButton("取消", callback_data=f"show_entry:{page_id}")]
        ]
        
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "update_reminder" and page_id:
        # 更新提醒状态
        reminder_value = data[2] == "True" if len(data) > 2 else False
        result = notion_manager.update_reminder_status(page_id, reminder_value)
        
        if result["success"]:
            await query.edit_message_text(
                f"{query.message.text}\n\n*提醒状态已更新为:* {'开启' if reminder_value else '关闭'}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回", callback_data=f"show_entry:{page_id}")]]),
                parse_mode='Markdown'
            )
        else:
            error_msg = escape_markdown(result.get('error', '未知错误'))
            await query.edit_message_text(
                f"{query.message.text}\n\n❌ 更新提醒状态失败: {error_msg}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回", callback_data=f"show_entry:{page_id}")]]),
                parse_mode='Markdown'
            )
    
    elif action == "filter_tag" and page_id:  # 这里的page_id实际上是tag
        tag = page_id  # 重命名更清晰
        
        # 告知用户正在加载
        escaped_tag = escape_markdown(tag)
        await query.edit_message_text(
            f"正在获取标签为 '{escaped_tag}' 的条目...",
            parse_mode='Markdown'
        )
        
        # 获取带有该标签的条目
        entries = notion_manager.get_entries_with_details(tag=tag)
        
        if not entries:
            await query.edit_message_text(
                f"没有找到带有标签 '{escaped_tag}' 的条目。",
                parse_mode='Markdown'
            )
            return
        
        # 创建条目列表
        message_text = f"*标签 '{escaped_tag}' 的条目:*\n\n"
        
        keyboard = []
        for entry in entries:
            title = escape_markdown(entry["title"] or "无标题")
            status = escape_markdown(entry["status"] or "未知状态")
            entry_id = entry["id"]
            
            # 添加条目信息
            message_text += f"• *{title}* ({status})\n"
            
            # 为每个条目添加一个按钮
            keyboard.append([InlineKeyboardButton(
                f"{title[:20]}...", 
                callback_data=f"show_entry:{entry_id}"
            )])
        
        # 添加返回按钮
        keyboard.append([InlineKeyboardButton("返回标签列表", callback_data="back_to_tags")])
        
        await query.edit_message_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif action == "show_entry":
        # 显示条目详细信息
        entry_id = page_id  # 重命名更清晰
        
        # 获取条目详细信息
        entries = notion_manager.get_entries_with_details()
        entry = next((e for e in entries if e["id"] == entry_id), None)
        
        if not entry:
            await query.edit_message_text(
                "无法获取条目信息。",
                parse_mode='Markdown'
            )
            return
        
        # 构建详细信息
        title = escape_markdown(entry["title"] or "无标题")
        summary = escape_markdown(entry["summary"] or "无摘要")
        status = escape_markdown(entry["status"] or "未知状态")
        tags = entry["tags"] or []
        tags_text = escape_markdown(", ".join(tags) if tags else "无标签")
        source = escape_markdown(entry["source"] or "无来源")
        url = entry["url"] or "#"
        reminder = entry.get("reminder", False)
        check_in_status = escape_markdown(entry.get("check_in_status", "否"))
        check_in_count = entry.get("check_in_count", 0)
        
        message_text = (
            f"*{title}*\n\n"
            f"*摘要:* {summary[:300]}...\n\n"
            f"*状态:* {status}\n"
            f"*标签:* {tags_text}\n"
            f"*来源:* {source}\n"
            f"*是否提醒:* {'是' if reminder else '否'}\n"
            f"*今日是否打卡:* {check_in_status}\n"
            f"*打卡次数:* {check_in_count}\n"
        )
        
        # 添加操作按钮
        keyboard = [
            [InlineKeyboardButton("更改状态", callback_data=f"status:{entry_id}")],
            [InlineKeyboardButton("添加标签", callback_data=f"add_tag:{entry_id}")],
            [InlineKeyboardButton("删除", callback_data=f"delete:{entry_id}")],
            [InlineKeyboardButton("查看原文", url=url)],
            [InlineKeyboardButton("今日是否打卡设置", callback_data=f"checkin_status:{entry_id}")],
            [InlineKeyboardButton("是否提醒设置", callback_data=f"set_reminder:{entry_id}")],
            [InlineKeyboardButton("返回", callback_data="back_to_tags")]
        ]
        
        await query.edit_message_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif action == "create_new_tag":
        # 准备创建新标签
        context.user_data["creating_new_tag"] = True
        
        await query.edit_message_text(
            "请输入要创建的新标签名称:",
            parse_mode='Markdown'
        )
    
    elif action == "back_to_tags":
        # 返回标签列表
        all_tags = notion_manager.get_all_tags()
        
        if not all_tags:
            await query.edit_message_text(
                "目前没有可用的标签。",
                parse_mode='Markdown'
            )
            return
        
        # 创建标签按钮
        keyboard = []
        row = []
        for i, tag in enumerate(all_tags):
            row.append(InlineKeyboardButton(tag, callback_data=f"filter_tag:{tag}"))
            if len(row) == 2 or i == len(all_tags) - 1:
                keyboard.append(row)
                row = []
        
        # 添加创建新标签的选项
        keyboard.append([InlineKeyboardButton("➕ 创建新标签", callback_data="create_new_tag")])
        
        await query.edit_message_text(
            "请选择要筛选的标签:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # 主菜单回调处理
    elif action == "menu_add_content":
        await query.edit_message_text(
            "*添加新内容*\n\n"
            "请直接发送要添加的链接，我将自动处理并保存到Notion。\n\n"
            "您也可以添加一段文本注释，链接会被自动识别。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")]]),
            parse_mode='Markdown'
        )
    
    elif action == "menu_tags":
        # 获取所有标签并显示
        all_tags = notion_manager.get_all_tags()
        
        if not all_tags:
            await query.edit_message_text(
                "*标签列表*\n\n"
                "目前没有可用的标签。\n\n"
                "您可以通过以下方式添加标签：\n"
                "1. 发送链接并处理内容时自动生成标签\n"
                "2. 为现有条目添加标签\n"
                "3. 直接创建一个新标签",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("创建新标签", callback_data="create_new_tag")],
                    [InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")]
                ]),
                parse_mode='Markdown'
            )
        else:
            # 创建标签按钮
            keyboard = []
            row = []
            for i, tag in enumerate(all_tags):
                row.append(InlineKeyboardButton(tag, callback_data=f"filter_tag:{tag}"))
                if len(row) == 2 or i == len(all_tags) - 1:
                    keyboard.append(row)
                    row = []
            
            keyboard.append([InlineKeyboardButton("➕ 创建新标签", callback_data="create_new_tag")])
            keyboard.append([InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")])
            
            await query.edit_message_text(
                "*标签列表*\n\n"
                "请选择要筛选的标签:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    elif action == "menu_search":
        await query.edit_message_text(
            "*搜索内容*\n\n"
            "请输入要搜索的关键词:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")]]),
            parse_mode='Markdown'
        )
        
        # 设置期望关键词输入
        context.user_data["expecting_search"] = True
    
    elif action == "menu_recent":
        # 获取最近添加的条目
        # 记录最近视图，用于删除等操作后返回
        context.user_data["last_view"] = "recent"
        entries = notion_manager.get_entries_with_details(limit=5)
        
        if not entries:
            await query.edit_message_text(
                "*最近添加*\n\n"
                "目前没有任何条目。",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")]]),
                parse_mode='Markdown'
            )
        else:
            # 创建条目列表
            message_text = "*最近添加的条目:*\n\n"
            
            keyboard = []
            for entry in entries:
                title = escape_markdown(entry["title"] or "无标题")
                status = escape_markdown(entry["status"] or "未知状态")
                entry_id = entry["id"]
                
                # 添加条目信息和摘要
                summary = escape_markdown(entry["summary"] or "无摘要")
                message_text += f"• *{title}* ({status})\n"
                message_text += f"  {summary[:100]}...\n\n"
                
                # 为每个条目添加一个按钮
                keyboard.append([InlineKeyboardButton(
                    f"{title[:20]}...", 
                    callback_data=f"show_entry:{entry_id}"
                )])
            
            # 添加返回菜单选项
            keyboard.append([InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")])
            
            await query.edit_message_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    elif action == "menu_checkin":
        # 获取需要打卡的条目
        entries = notion_manager.get_reminder_entries()
        
        if not entries:
            await query.edit_message_text(
                "*打卡管理*\n\n"
                "目前没有需要打卡的条目。\n\n"
                "您可以为任意条目设置打卡提醒。",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")]]),
                parse_mode='Markdown'
            )
        else:
            # 创建打卡条目列表
            message_text = "*打卡管理*\n\n需要打卡的条目:\n\n"
            
            keyboard = []
            for entry in entries:
                title = entry["title"] or "无标题"
                check_in_status = entry.get("check_in_status", "否")
                check_in_count = entry.get("check_in_count", 0)
                entry_id = entry["id"]
                
                # 添加条目信息
                message_text += f"• *{title}*\n"
                message_text += f"  当前状态: {check_in_status}, 打卡次数: {check_in_count}\n\n"
                
                # 为每个条目添加一个按钮
                keyboard.append([InlineKeyboardButton(
                    f"管理 {title[:15]}...", 
                    callback_data=f"show_entry:{entry_id}"
                )])
            
            # 添加返回菜单选项
            keyboard.append([InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")])
            
            await query.edit_message_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    elif action == "menu_settings":
        # 设置菜单
        keyboard = [
            [InlineKeyboardButton("管理标签", callback_data="menu_tags")],
            [InlineKeyboardButton("打卡提醒设置", callback_data="menu_checkin")],
            [InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            "*设置*\n\n"
            "请选择要管理的设置项:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif action == "menu_help":
        # 显示帮助信息
        await query.edit_message_text(
            HELP_MESSAGE + "\n\n[点击这里返回主菜单]",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")]]),
            parse_mode='Markdown'
        )
    
    elif action == "back_to_menu":
        # 返回主菜单消息但不更改底部键盘
        await query.edit_message_text(
            "📋 *主菜单*\n\n"
            "请选择您需要的功能:\n\n"
            "底部键盘菜单已准备就绪，您可以随时点击底部的菜单按钮。",
            parse_mode='Markdown'
        )
    
    elif action == "cancel":
        # 恢复原始消息和按钮
        if "original_message" in context.user_data and "original_markup" in context.user_data:
            await query.edit_message_text(
                context.user_data["original_message"],
                reply_markup=context.user_data["original_markup"],
                parse_mode='Markdown'
            )
        else:
            # 如果没有原始消息记录，返回主菜单
            keyboard = []
            for option in MAIN_MENU_OPTIONS:
                keyboard.append([InlineKeyboardButton(option["text"], callback_data=option["callback"])])
            
            await query.edit_message_text(
                "📋 *主菜单*\n\n"
                "请选择您需要的功能:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

async def process_tag_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理用户输入的标签、搜索关键词或链接"""
    message_text = update.message.text.strip() if update.message and update.message.text else ""
    
    # 检查是否是主菜单选项
    menu_text_to_callback = {option["text"]: option["callback"] for option in MAIN_MENU_OPTIONS}
    if message_text in menu_text_to_callback:
        # 模拟一个回调查询
        callback_data = menu_text_to_callback[message_text]
        
        # 创建一个简单的消息回复来代替编辑现有消息
        if callback_data == "menu_add_content":
            await update.message.reply_text(
                "*添加新内容*\n\n"
                "请直接发送要添加的链接，我将自动处理并保存到Notion。\n\n"
                "您也可以添加一段文本注释，链接会被自动识别。",
                parse_mode='Markdown'
            )
        elif callback_data == "menu_tags":
            # 获取所有标签
            all_tags = notion_manager.get_all_tags()
            
            if not all_tags:
                await update.message.reply_text(
                    "*标签列表*\n\n"
                    "目前没有可用的标签。\n\n"
                    "您可以通过以下方式添加标签：\n"
                    "1. 发送链接并处理内容时自动生成标签\n"
                    "2. 为现有条目添加标签\n"
                    "3. 直接创建一个新标签",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("创建新标签", callback_data="create_new_tag")]
                    ]),
                    parse_mode='Markdown'
                )
            else:
                # 创建标签按钮
                keyboard = []
                row = []
                for i, tag in enumerate(all_tags):
                    row.append(InlineKeyboardButton(tag, callback_data=f"filter_tag:{tag}"))
                    if len(row) == 2 or i == len(all_tags) - 1:
                        keyboard.append(row)
                        row = []
                
                keyboard.append([InlineKeyboardButton("➕ 创建新标签", callback_data="create_new_tag")])
                
                await update.message.reply_text(
                    "*标签列表*\n\n"
                    "请选择要筛选的标签:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        elif callback_data == "menu_search":
            await update.message.reply_text(
                "*搜索内容*\n\n"
                "请输入要搜索的关键词:",
                parse_mode='Markdown'
            )
            
            # 设置期望关键词输入
            context.user_data["expecting_search"] = True
        elif callback_data == "menu_recent":
            # 获取最近添加的条目
            entries = notion_manager.get_entries_with_details(limit=5)
            
            if not entries:
                await update.message.reply_text(
                    "*最近添加*\n\n"
                    "目前没有任何条目。",
                    parse_mode='Markdown'
                )
            else:
                # 创建条目列表
                message_text = "*最近添加的条目:*\n\n"
                
                keyboard = []
                for entry in entries:
                    title = entry["title"] or "无标题"
                    status = entry["status"] or "未知状态"
                    entry_id = entry["id"]
                    
                    # 添加条目信息和摘要
                    summary = entry["summary"] or "无摘要"
                    message_text += f"• *{title}* ({status})\n"
                    message_text += f"  {summary[:100]}...\n\n"
                    
                    # 为每个条目添加一个按钮
                    keyboard.append([InlineKeyboardButton(
                        f"{title[:20]}...", 
                        callback_data=f"show_entry:{entry_id}"
                    )])
                
                # 添加返回菜单选项
                keyboard.append([InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")])
                
                await update.message.reply_text(
                    message_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        elif callback_data == "menu_checkin":
            # 获取需要打卡的条目
            entries = notion_manager.get_reminder_entries()
            
            if not entries:
                await update.message.reply_text(
                    "*打卡管理*\n\n"
                    "目前没有需要打卡的条目。\n\n"
                    "您可以为任意条目设置打卡提醒。",
                    parse_mode='Markdown'
                )
            else:
                # 创建打卡条目列表
                message_text = "*打卡管理*\n\n需要打卡的条目:\n\n"
                
                keyboard = []
                for entry in entries:
                    title = entry["title"] or "无标题"
                    check_in_status = entry.get("check_in_status", "否")
                    check_in_count = entry.get("check_in_count", 0)
                    entry_id = entry["id"]
                    
                    # 添加条目信息
                    message_text += f"• *{title}*\n"
                    message_text += f"  当前状态: {check_in_status}, 打卡次数: {check_in_count}\n\n"
                    
                    # 为每个条目添加一个按钮
                    keyboard.append([InlineKeyboardButton(
                        f"管理 {title[:15]}...", 
                        callback_data=f"show_entry:{entry_id}"
                    )])
                
                # 添加返回菜单选项
                keyboard.append([InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")])
                
                await update.message.reply_text(
                    message_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        elif callback_data == "menu_settings":
            # 设置菜单
            keyboard = [
                [InlineKeyboardButton("管理标签", callback_data="menu_tags")],
                [InlineKeyboardButton("打卡提醒设置", callback_data="menu_checkin")],
                [InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")]
            ]
            
            await update.message.reply_text(
                "*设置*\n\n"
                "请选择要管理的设置项:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        elif callback_data == "menu_help":
            # 显示帮助信息
            await update.message.reply_text(
                HELP_MESSAGE + "\n\n[点击这里返回主菜单]",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("返回主菜单", callback_data="back_to_menu")]]),
                parse_mode='Markdown'
            )
        
        return
    
    # 检查是否期望标签输入
    if context.user_data.get("expecting_tag", False):
        page_id = context.user_data.get("current_page_id")
        tag = message_text
        
        if page_id and tag:
            # 添加标签
            result = notion_manager.add_tag_to_entry(page_id, tag)
            
            if result["success"]:
                await update.message.reply_text(
                    f"✅ 标签 '{tag}' 已成功添加到条目!",
                    parse_mode='Markdown'
                )
            else:
                error_msg = escape_markdown(result.get('error', '未知错误'))
                await update.message.reply_text(
                    f"❌ 添加标签失败: {error_msg}",
                    parse_mode='Markdown'
                )
                
            # 重置状态
            context.user_data["expecting_tag"] = False
            context.user_data["current_page_id"] = None
        else:
            await update.message.reply_text(
                "❌ 无效的标签或条目ID。请重试。",
                parse_mode='Markdown'
            )
    
    # 检查是否正在创建新标签
    elif context.user_data.get("creating_new_tag", False):
        new_tag = message_text
        
        if not new_tag:
            await update.message.reply_text(
                "❌ 标签名称不能为空。请重试。",
                parse_mode='Markdown'
            )
            return
            
        # 在这里，我们仅记录标签创建尝试，因为Notion实际上会在添加时自动创建新标签
        # 要确认标签是否创建成功，我们可以尝试获取随机ID并尝试添加标签，或者创建一个带有该标签的临时页面
        
        await update.message.reply_text(
            f"✅ 标签 '{new_tag}' 已创建！\n\n"
            f"提示：标签将在您首次将其添加到条目时正式在Notion中创建。\n"
            f"您可以使用 /tags 命令查看所有可用标签。",
            parse_mode='Markdown'
        )
        
        # 重置状态
        context.user_data["creating_new_tag"] = False
    
    # 检查是否期望搜索关键词
    elif context.user_data.get("expecting_search", False):
        keyword = message_text
        
        if not keyword:
            await update.message.reply_text(
                "❌ 搜索关键词不能为空。请重试。",
                parse_mode='Markdown'
            )
            return
        
        # 显示正在搜索信息
        loading_message = await update.message.reply_text(
            f"正在搜索包含 '{keyword}' 的条目...",
            parse_mode='Markdown'
        )
        
        # 这里我们需要一个搜索功能，但当前的API不直接支持
        # 作为替代，我们获取所有条目并进行本地搜索
        entries = notion_manager.get_entries_with_details(limit=20)
        
        # 过滤包含关键词的条目
        filtered_entries = []
        for entry in entries:
            title = entry["title"] or ""
            summary = entry["summary"] or ""
            if keyword.lower() in title.lower() or keyword.lower() in summary.lower():
                filtered_entries.append(entry)
        
        if not filtered_entries:
            escaped_keyword = escape_markdown(keyword)
            await loading_message.edit_text(
                f"没有找到包含 '{escaped_keyword}' 的条目。",
                parse_mode='Markdown'
            )
            # 重置状态
            context.user_data["expecting_search"] = False
            return
        
        # 创建条目列表
        escaped_keyword = escape_markdown(keyword)
        message_text = f"*搜索 '{escaped_keyword}' 的结果:*\n\n"
        
        keyboard = []
        for entry in filtered_entries:
            title = escape_markdown(entry["title"] or "无标题")
            status = escape_markdown(entry["status"] or "未知状态")
            entry_id = entry["id"]
            
            # 添加条目信息
            message_text += f"• *{title}* ({status})\n"
            
            # 为每个条目添加一个按钮
            keyboard.append([InlineKeyboardButton(
                f"{title[:20]}...", 
                callback_data=f"show_entry:{entry_id}"
            )])
        
        await loading_message.edit_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # 重置状态
        context.user_data["expecting_search"] = False
        
    else:
        # 如果不是期望的标签输入或搜索关键词，则检查是否是链接
        if re.search(r'https?://\S+', message_text):
            await process_link(update, context)

async def list_tags(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """列出所有可用标签并允许按标签筛选"""
    # 告知用户正在加载
    loading_message = await update.message.reply_text("正在加载标签列表...")
    
    # 从Notion数据库获取所有唯一标签
    all_tags = notion_manager.get_all_tags()
    
    if not all_tags:
        # 如果没有标签，提供一个创建标签的选项
        await loading_message.edit_text(
            "目前没有可用的标签。\n\n"
            "您可以通过以下方式添加标签：\n"
            "1. 发送链接并处理内容时自动生成标签\n"
            "2. 为现有条目添加标签\n"
            "3. 直接创建一个新标签"
        )
        keyboard = [
            [InlineKeyboardButton("创建新标签", callback_data="create_new_tag")]
        ]
        await update.message.reply_text(
            "您想要创建新标签吗？",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # 创建标签按钮
    keyboard = []
    row = []
    for i, tag in enumerate(all_tags):
        row.append(InlineKeyboardButton(tag, callback_data=f"filter_tag:{tag}"))
        if len(row) == 2 or i == len(all_tags) - 1:
            keyboard.append(row)
            row = []
    
    # 添加创建新标签的选项
    keyboard.append([InlineKeyboardButton("➕ 创建新标签", callback_data="create_new_tag")])
    
    await loading_message.delete()
    await update.message.reply_text(
        "请选择要筛选的标签:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理/status命令，列出条目状态选项"""
    # 显示状态选择指南
    await update.message.reply_text(
        "要更改条目状态，请先找到相应条目，然后使用'更改状态'按钮。\n\n"
        "可用的状态包括:\n"
        "- 未处理: 新添加的条目\n"
        "- 进行中: 正在处理或阅读的条目\n"
        "- 已完成: 已处理完成的条目\n"
        "- 已放弃: 决定不再处理的条目"
    )

async def show_recent_entries(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """显示最近添加的条目"""
    # 告知用户正在加载
    loading_message = await update.message.reply_text("正在获取最近添加的条目...")
    
    # 记录最近视图，用于删除等操作后返回
    context.user_data["last_view"] = "recent"

    # 获取最近添加的条目
    entries = notion_manager.get_entries_with_details(limit=5)
    
    if not entries:
        await loading_message.edit_text("目前没有任何条目。")
        return
    
    # 创建条目列表
    message_text = "*最近添加的条目:*\n\n"
    keyboard = []
    for entry in entries:
        title = escape_markdown(entry["title"] or "无标题")
        status = escape_markdown(entry["status"] or "未知状态")
        entry_id = entry["id"]
        summary = escape_markdown(entry["summary"] or "无摘要")
        message_text += f"• *{title}* ({status})\n"
        message_text += f"  {summary[:100]}...\n\n"
        keyboard.append([InlineKeyboardButton(
            f"{title[:20]}...",
            callback_data=f"show_entry:{entry_id}"
        )])
    keyboard.append([InlineKeyboardButton("按标签筛选", callback_data="back_to_tags")])
    await loading_message.edit_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """设置是否提醒"""
    page_id = context.user_data.get("current_page_id")
    if not page_id:
        await update.message.reply_text("请先选择一个条目后再设置提醒。", parse_mode='Markdown')
        return
    # 获取当前提醒状态
    entries = notion_manager.get_entries_with_details(limit=1)
    entry = next((e for e in entries if e["id"] == page_id), None)
    current_status = entry.get("reminder", False) if entry else False
    new_status = not current_status
    result = notion_manager.update_reminder_status(page_id, new_status)
    if result.get("success"):
        await update.message.reply_text(f"提醒状态已{'开启' if new_status else '关闭'}。", parse_mode='Markdown')
    else:
        error_msg = escape_markdown(result.get('error', '未知错误'))
        await update.message.reply_text(f"提醒状态更新失败: {error_msg}", parse_mode='Markdown')

async def check_in(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """标记今日是否打卡"""
    page_id = context.user_data.get("current_page_id")
    if not page_id:
        await update.message.reply_text("请先选择一个条目后再打卡。", parse_mode='Markdown')
        return
    # 标记今日打卡
    result = notion_manager.update_check_in_status(page_id, True)
    if result.get("success"):
        notion_manager.increment_check_in_count(page_id)
        await update.message.reply_text("今日打卡成功！已为该条目增加一次打卡计数。", parse_mode='Markdown')
    else:
        error_msg = escape_markdown(result.get('error', '未知错误'))
        await update.message.reply_text(f"打卡失败: {error_msg}", parse_mode='Markdown')

async def check_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查看打卡次数"""
    page_id = context.user_data.get("current_page_id")
    if not page_id:
        await update.message.reply_text("请先选择一个条目后再查看打卡次数。", parse_mode='Markdown')
        return
    # 获取打卡次数
    entries = notion_manager.get_entries_with_details(limit=1)
    entry = next((e for e in entries if e["id"] == page_id), None)
    count = entry.get("check_in_count", 0) if entry else 0
    await update.message.reply_text(f"当前条目打卡次数：{count}", parse_mode='Markdown')

async def search_entries(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """搜索条目"""
    await update.message.reply_text(
        "请输入要搜索的关键词:",
        parse_mode='Markdown'
    )
    
    # 设置期望关键词输入
    context.user_data["expecting_search"] = True

async def setup_commands(application) -> None:
    """设置命令菜单，这将在Telegram客户端的输入框左侧显示菜单按钮"""
    commands = [
        BotCommand("start", "开始使用机器人"),
        BotCommand("menu", "显示主菜单"),
        BotCommand("mymenu", "我的菜单快捷方式"),
        BotCommand("help", "显示帮助信息"),
        BotCommand("tags", "列出所有标签"),
        BotCommand("status", "更改条目状态"),
        BotCommand("reminder", "设置是否提醒"),
        BotCommand("checkin", "标记今日是否完成打卡"),
        BotCommand("checkcount", "查看打卡次数"),
        BotCommand("recent", "显示最近添加的条目"),
        BotCommand("search", "搜索条目")
    ]
    
    try:
        await application.bot.set_my_commands(commands)
        logger.info("已成功设置命令菜单，现在用户可以在输入框左侧看到菜单按钮")
    except Exception as e:
        logger.error(f"设置命令菜单失败: {str(e)}")

async def post_init(application: Application) -> None:
    """应用初始化后运行的函数"""
    await setup_commands(application)

def main() -> None:
    """启动机器人"""
    # 创建应用实例 - 确保TOKEN不为None
    token = TELEGRAM_BOT_TOKEN
    if not token:
        raise ValueError("Telegram Bot Token不能为空！请检查环境变量设置。")
    
    application = Application.builder().token(token).build()

    # 添加处理程序
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))  # 添加菜单命令
    application.add_handler(CommandHandler("mymenu", my_menu_command))  # 添加"我的菜单"命令
    application.add_handler(CommandHandler("tags", list_tags))
    application.add_handler(CommandHandler("status", handle_status_command))
    application.add_handler(CommandHandler("recent", show_recent_entries))
    application.add_handler(CommandHandler("reminder", set_reminder))
    application.add_handler(CommandHandler("checkin", check_in))
    application.add_handler(CommandHandler("checkcount", check_count))
    application.add_handler(CommandHandler("search", search_entries))
    
    # 处理回调查询
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # 处理消息（包括菜单选择和其他文本消息）
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_tag_input))

    # 启动机器人，并在启动后设置命令菜单
    application.post_init = post_init
    
    # 记录日志
    logger.info("正在启动机器人，将设置命令菜单...")
    
    # 启动应用
    application.run_polling()

if __name__ == '__main__':
    main()