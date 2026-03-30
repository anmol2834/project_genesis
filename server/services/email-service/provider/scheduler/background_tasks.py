"""
Background Task Manager
Manages long-running background tasks for email monitoring.
"""

import asyncio
from typing import Optional

from shared.logger import get_logger
from provider.scheduler.subscription_scheduler import SubscriptionScheduler
from provider.scheduler.smtp_poller import SMTPPoller

logger = get_logger(__name__)


class BackgroundTaskManager:
    """Manages background tasks for email monitoring."""

    def __init__(self):
        self.subscription_scheduler = SubscriptionScheduler()
        self.smtp_poller = SMTPPoller()
        self.scheduler_task: Optional[asyncio.Task] = None
        self.poller_task: Optional[asyncio.Task] = None

    async def start_all(self):
        """Start all background tasks."""
        self.scheduler_task = asyncio.create_task(
            self.subscription_scheduler.start_scheduler()
        )
        self.poller_task = asyncio.create_task(
            self.smtp_poller.start_polling()
        )

    async def stop_all(self):
        """Stop all background tasks."""
        logger.info("Stopping background tasks")

        # Stop subscription scheduler
        await self.subscription_scheduler.stop_scheduler()
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass

        # Stop SMTP poller
        await self.smtp_poller.stop_polling()
        if self.poller_task:
            self.poller_task.cancel()
            try:
                await self.poller_task
            except asyncio.CancelledError:
                pass

        logger.info("All background tasks stopped")

    def get_status(self) -> dict:
        """Get status of all background tasks."""
        return {
            "subscription_scheduler": {
                "running": self.subscription_scheduler.is_running,
                "task_alive": self.scheduler_task and not self.scheduler_task.done()
            },
            "smtp_poller": {
                "running": self.smtp_poller.is_running,
                "task_alive": self.poller_task and not self.poller_task.done()
            }
        }


# Global instance
_task_manager: Optional[BackgroundTaskManager] = None


def get_task_manager() -> BackgroundTaskManager:
    """Get or create global task manager instance."""
    global _task_manager
    if _task_manager is None:
        _task_manager = BackgroundTaskManager()
    return _task_manager
