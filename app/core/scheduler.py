from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import re
from app.services.notion_service import NotionManager
from app.config import TELEGRAM_BOT_TOKEN,TARGET_CHAT_ID
from telegram import Bot

def escape_markdown(text):
    """转义 Telegram Markdown V1 特殊字符"""
    if not text:
        return ""
    # Telegram Markdown V1 需要转义 _ * [ ] ( ) ~ ` > # + - = | { } . !
    return re.sub(r'([_\*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

# 初始化 Notion 管理器和 Telegram Bot
notion_manager = NotionManager()
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def check_and_notify():
    entries = notion_manager.get_reminder_entries()
    if entries:
        msg = "以下内容还未打卡，请及时完成：\n"
        for entry in entries:
            title = escape_markdown(entry["title"] or "无标题")
            check_in_status = entry.get("check_in_status", "否")
            if check_in_status != "是":
                msg += f"- {title}\n"
        if msg.strip() != "以下内容还未打卡，请及时完成：":
            bot.send_message(chat_id=TARGET_CHAT_ID, text=msg)

scheduler = BackgroundScheduler()
scheduler.add_job(check_and_notify, 'cron', day_of_week='mon-fri', hour=18, minute=0)
scheduler.add_job(check_and_notify, 'cron', day_of_week='sat,sun', hour=12, minute=0)
scheduler.start()