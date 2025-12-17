"""
Scheduler for automatic news fetching
"""
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from aggregator import NewsAggregator


class NewsScheduler:
    """Scheduled news aggregation"""
    
    def __init__(self):
        self.aggregator = NewsAggregator()
        self.scheduler = AsyncIOScheduler()
    
    async def fetch_job(self):
        """Job to fetch news"""
        print(f"\n⏰ Scheduled fetch started at {datetime.now().isoformat()}")
        try:
            result = await self.aggregator.run()
            print(f"⏰ Scheduled fetch completed: {result['new_articles']} new articles")
        except Exception as e:
            print(f"⏰ Scheduled fetch error: {e}")
    
    def start_interval(self, minutes: int = 30):
        """Start fetching at regular intervals"""
        self.scheduler.add_job(
            self.fetch_job,
            trigger=IntervalTrigger(minutes=minutes),
            id='news_fetch',
            replace_existing=True,
            max_instances=1
        )
        self.scheduler.start()
        print(f"📅 Scheduler started: fetching every {minutes} minutes")
    
    def start_cron(self, hour: str = "*/2", minute: str = "0"):
        """Start fetching on a cron schedule"""
        self.scheduler.add_job(
            self.fetch_job,
            trigger=CronTrigger(hour=hour, minute=minute),
            id='news_fetch',
            replace_existing=True,
            max_instances=1
        )
        self.scheduler.start()
        print(f"📅 Scheduler started: cron {hour}:{minute}")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        print("📅 Scheduler stopped")


async def run_scheduler():
    """Run the scheduler"""
    import sys
    
    scheduler = NewsScheduler()
    
    # Parse command line arguments
    interval = 30  # Default: every 30 minutes
    if len(sys.argv) > 1:
        try:
            interval = int(sys.argv[1])
        except ValueError:
            pass
    
    # Run initial fetch
    print("🚀 Running initial fetch...")
    await scheduler.fetch_job()
    
    # Start scheduler
    scheduler.start_interval(minutes=interval)
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        scheduler.stop()
        print("\n👋 Scheduler stopped by user")


if __name__ == '__main__':
    asyncio.run(run_scheduler())
