from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class JobsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "jobs"

    def ready(self):
        """Initialize the background scheduler when Django starts."""
        # Only start scheduler in production or when explicitly requested
        import os

        # Don't start scheduler during migrations or management commands
        if os.environ.get("RUN_MAIN") == "true" or "runserver" not in os.environ.get(
            "DJANGO_SETTINGS_MODULE", ""
        ):

            # Check if we should auto-start the scheduler
            auto_start = (
                os.environ.get("AUTO_START_SCHEDULER", "false").lower() == "true"
            )

            if auto_start:
                try:
                    from .scheduler import start_scheduler

                    start_scheduler()
                    logger.info("Background scheduler started automatically")
                except Exception as e:
                    logger.error(f"Failed to start background scheduler: {e}")
