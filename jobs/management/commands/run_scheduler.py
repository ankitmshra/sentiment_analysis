"""
Django management command to run the sentiment analysis background scheduler.

This command starts the APScheduler-based background job system that handles
data synchronization, sentiment calculation, and analysis tasks.
"""

import signal
import sys
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from jobs.scheduler import get_scheduler, start_scheduler, stop_scheduler


class Command(BaseCommand):
    help = "Run the sentiment analysis background job scheduler"

    def add_arguments(self, parser):
        parser.add_argument(
            "--test-run",
            action="store_true",
            help="Run scheduler for a short test period and exit",
        )
        parser.add_argument(
            "--run-once",
            action="store_true",
            help="Run all jobs once and exit (for testing)",
        )

    def handle(self, *args, **options):
        test_run = options["test_run"]
        run_once = options["run_once"]

        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            self.stdout.write(
                self.style.WARNING("Received shutdown signal, stopping scheduler...")
            )
            stop_scheduler()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            if run_once:
                self.run_jobs_once()
            else:
                self.run_scheduler(test_run)

        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("Keyboard interrupt received, stopping scheduler...")
            )
            stop_scheduler()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Scheduler error: {e}"))
            stop_scheduler()
            raise

    def run_scheduler(self, test_run=False):
        """Run the background scheduler."""
        self.stdout.write(
            self.style.SUCCESS("Starting sentiment analysis background scheduler...")
        )

        # Start the scheduler
        start_scheduler()

        # Get scheduler instance for status monitoring
        scheduler = get_scheduler()

        # Display initial status
        status = scheduler.get_job_status()
        self.stdout.write(f"Scheduler status: {status['status']}")
        self.stdout.write(f"Scheduled jobs: {len(status['jobs'])}")

        for job in status["jobs"]:
            self.stdout.write(f"  - {job['name']} (ID: {job['id']})")
            if job["next_run_time"]:
                self.stdout.write(f"    Next run: {job['next_run_time']}")

        if test_run:
            # Run for 2 minutes for testing
            self.stdout.write(
                self.style.WARNING("Test run mode: will stop after 2 minutes")
            )
            time.sleep(120)
            self.stdout.write(
                self.style.SUCCESS("Test run completed, stopping scheduler")
            )
            stop_scheduler()
        else:
            # Run indefinitely
            self.stdout.write(
                self.style.SUCCESS("Scheduler running. Press Ctrl+C to stop.")
            )

            try:
                while True:
                    time.sleep(60)  # Check status every minute
                    status = scheduler.get_job_status()
                    if status["status"] != "running":
                        self.stdout.write(
                            self.style.ERROR("Scheduler stopped unexpectedly")
                        )
                        break

            except KeyboardInterrupt:
                pass
            finally:
                stop_scheduler()

    def run_jobs_once(self):
        """Run all jobs once for testing."""
        self.stdout.write(self.style.SUCCESS("Running all jobs once for testing..."))

        from jobs.tasks import (
            sync_data_from_source,
            calculate_sentiment_scores,
            calculate_segment_sentiment,
            calculate_overall_sentiment,
        )

        # Run data sync task
        self.stdout.write("Running data sync task...")
        try:
            sync_data_from_source()
            self.stdout.write(self.style.SUCCESS("Data sync completed successfully"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Data sync failed: {e}"))

        # Wait a moment between tasks
        time.sleep(2)

        # Run sentiment calculation task
        self.stdout.write("Running sentiment calculation task...")
        try:
            calculate_sentiment_scores()
            self.stdout.write(
                self.style.SUCCESS("Sentiment calculation completed successfully")
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Sentiment calculation failed: {e}"))

        # Wait a moment between tasks
        time.sleep(2)

        # Run segment analysis task
        self.stdout.write("Running segment analysis task...")
        try:
            calculate_segment_sentiment()
            self.stdout.write(
                self.style.SUCCESS("Segment analysis completed successfully")
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Segment analysis failed: {e}"))

        # Wait a moment between tasks
        time.sleep(2)

        # Run overall sentiment task
        self.stdout.write("Running overall sentiment task...")
        try:
            calculate_overall_sentiment()
            self.stdout.write(
                self.style.SUCCESS("Overall sentiment completed successfully")
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Overall sentiment failed: {e}"))

        self.stdout.write(self.style.SUCCESS("All jobs completed successfully!"))
