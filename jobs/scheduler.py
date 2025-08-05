"""
Background job scheduler for sentiment analysis system.

This module handles the scheduling and execution of background jobs
including data sync, sentiment calculation, and aggregation tasks.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.utils import timezone
from config.models import JobConfig

logger = logging.getLogger(__name__)


class SentimentJobScheduler:
    """
    Main scheduler for sentiment analysis background jobs.

    Manages the execution of:
    1. Data sync jobs (hourly)
    2. Sentiment calculation jobs
    3. Segment analysis jobs
    4. Overall sentiment calculation jobs
    """

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.is_running = False
        self.job_config = None

    def start(self):
        """Start the background scheduler."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        try:
            # Load job configuration
            self.job_config = JobConfig.get_active_config()

            # Schedule jobs
            self._schedule_sync_jobs()
            self._schedule_sentiment_jobs()
            self._schedule_segment_jobs()
            self._schedule_overall_jobs()

            # Start scheduler
            self.scheduler.start()
            self.is_running = True

            logger.info("Sentiment job scheduler started successfully")

        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise

    def stop(self):
        """Stop the background scheduler."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return

        try:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("Sentiment job scheduler stopped")

        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
            raise

    def _schedule_sync_jobs(self):
        """Schedule data synchronization jobs."""
        if not self.job_config:
            return

        # Schedule hourly sync job
        self.scheduler.add_job(
            func=self._run_sync_job,
            trigger=IntervalTrigger(minutes=self.job_config.sync_interval_minutes),
            id="data_sync_job",
            name="Data Synchronization Job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        logger.info(
            f"Scheduled sync job every {self.job_config.sync_interval_minutes} minutes"
        )

    def _schedule_sentiment_jobs(self):
        """Schedule sentiment calculation jobs."""
        if not self.job_config:
            return

        # Schedule sentiment calculation job (runs after sync job)
        delay_minutes = self.job_config.sentiment_delay_minutes

        self.scheduler.add_job(
            func=self._run_sentiment_job,
            trigger=IntervalTrigger(minutes=self.job_config.sync_interval_minutes),
            id="sentiment_calculation_job",
            name="Sentiment Calculation Job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            # Start with delay after sync job
            next_run_time=timezone.now() + timedelta(minutes=delay_minutes),
        )

        logger.info(f"Scheduled sentiment job with {delay_minutes} minute delay")

    def _schedule_segment_jobs(self):
        """Schedule segment analysis jobs."""
        if not self.job_config:
            return

        delay_minutes = self.job_config.segment_delay_minutes

        self.scheduler.add_job(
            func=self._run_segment_job,
            trigger=IntervalTrigger(minutes=self.job_config.sync_interval_minutes),
            id="segment_analysis_job",
            name="Segment Analysis Job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=timezone.now() + timedelta(minutes=delay_minutes),
        )

        logger.info(f"Scheduled segment job with {delay_minutes} minute delay")

    def _schedule_overall_jobs(self):
        """Schedule overall sentiment calculation jobs."""
        if not self.job_config:
            return

        delay_minutes = self.job_config.overall_delay_minutes

        self.scheduler.add_job(
            func=self._run_overall_job,
            trigger=IntervalTrigger(minutes=self.job_config.sync_interval_minutes),
            id="overall_sentiment_job",
            name="Overall Sentiment Job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=timezone.now() + timedelta(minutes=delay_minutes),
        )

        logger.info(f"Scheduled overall job with {delay_minutes} minute delay")

    def _run_sync_job(self):
        """Execute data synchronization job."""
        from .tasks import sync_data_from_source

        logger.info("Starting data sync job")

        try:
            sync_data_from_source()
            logger.info("Data sync job completed successfully")

        except Exception as e:
            logger.error(f"Data sync job failed: {e}")
            raise

    def _run_sentiment_job(self):
        """Execute sentiment calculation job."""
        from .tasks import calculate_sentiment_scores

        logger.info("Starting sentiment calculation job")

        try:
            calculate_sentiment_scores()
            logger.info("Sentiment calculation job completed successfully")

        except Exception as e:
            logger.error(f"Sentiment calculation job failed: {e}")
            raise

    def _run_segment_job(self):
        """Execute segment analysis job."""
        from .tasks import calculate_segment_sentiment

        logger.info("Starting segment analysis job")

        try:
            calculate_segment_sentiment()
            logger.info("Segment analysis job completed successfully")

        except Exception as e:
            logger.error(f"Segment analysis job failed: {e}")
            raise

    def _run_overall_job(self):
        """Execute overall sentiment calculation job."""
        from .tasks import calculate_overall_sentiment

        logger.info("Starting overall sentiment job")

        try:
            calculate_overall_sentiment()
            logger.info("Overall sentiment job completed successfully")

        except Exception as e:
            logger.error(f"Overall sentiment job failed: {e}")
            raise

    def get_job_status(self) -> Dict[str, Any]:
        """Get status of all scheduled jobs."""
        if not self.is_running:
            return {"status": "stopped", "jobs": []}

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": (
                        job.next_run_time.isoformat() if job.next_run_time else None
                    ),
                    "trigger": str(job.trigger),
                }
            )

        return {
            "status": "running",
            "jobs": jobs,
            "scheduler_state": self.scheduler.state,
        }

    def run_job_now(self, job_id: str) -> bool:
        """Manually trigger a specific job."""
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.modify(next_run_time=timezone.now())
                logger.info(f"Manually triggered job: {job_id}")
                return True
            else:
                logger.warning(f"Job not found: {job_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to trigger job {job_id}: {e}")
            return False


# Global scheduler instance
_scheduler_instance = None


def get_scheduler() -> SentimentJobScheduler:
    """Get the global scheduler instance."""
    global _scheduler_instance

    if _scheduler_instance is None:
        _scheduler_instance = SentimentJobScheduler()

    return _scheduler_instance


def start_scheduler():
    """Start the global scheduler."""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """Stop the global scheduler."""
    scheduler = get_scheduler()
    scheduler.stop()
