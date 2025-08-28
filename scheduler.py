from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import telegram_bot  # 你的 Telegram 机器人模块
import notion_db     # 你的 Notion 数据库模块

def check_and_notify():
    today = datetime.now().date()
    items = notion_db.get_items_to_remind(today)
    if items:
        msg = "以下内容还未打卡，请及时完成：\n" + "\n".join([f"- {item['title']}" for item in items])
        telegram_bot.send_reminder(msg)

scheduler = BackgroundScheduler()

# 工作日 18:00
scheduler.add_job(check_and_notify, 'cron', day_of_week='mon-fri', hour=18, minute=0)
# 周末 12:00
scheduler.add_job(check_and_notify, 'cron', day_of_week='sat,sun', hour=12, minute=0)

scheduler.start()