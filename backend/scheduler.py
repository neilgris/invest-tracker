from apscheduler.schedulers.background import BackgroundScheduler
from services.market import fetch_and_save_daily


scheduler = BackgroundScheduler()


def start_scheduler():
    """启动定时任务：每个交易日15:30拉取行情"""
    # 周一到周五 15:30 执行
    scheduler.add_job(
        fetch_and_save_daily,
        "cron",
        day_of_week="mon-fri",
        hour=15,
        minute=30,
        id="daily_snapshot",
        replace_existing=True,
    )
    scheduler.start()
