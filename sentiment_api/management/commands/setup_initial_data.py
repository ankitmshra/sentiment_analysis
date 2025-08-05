"""
Django management command to set up initial configuration data.

This command creates default configurations for database connections,
sentiment analysis, job settings, and industry baselines.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from config.models import DatabaseConfig, SentimentConfig, JobConfig
from sentiment_api.models import IndustryBaseline


class Command(BaseCommand):
    help = "Set up initial configuration data for the sentiment analysis system"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reset existing configurations (delete and recreate)",
        )

    def handle(self, *args, **options):
        reset = options["reset"]

        if reset:
            self.stdout.write(
                self.style.WARNING("Resetting existing configurations...")
            )
            DatabaseConfig.objects.all().delete()
            SentimentConfig.objects.all().delete()
            JobConfig.objects.all().delete()
            IndustryBaseline.objects.all().delete()

        with transaction.atomic():
            # Create default database configuration
            self.create_database_configs()

            # Create default sentiment configuration
            self.create_sentiment_configs()

            # Create default job configuration
            self.create_job_configs()

            # Create industry baselines
            self.create_industry_baselines()

        self.stdout.write(
            self.style.SUCCESS("Successfully set up initial configuration data!")
        )

    def create_database_configs(self):
        """Create default database configurations."""
        self.stdout.write("Creating database configurations...")

        # Default configuration matching the user's requirements
        default_config, created = DatabaseConfig.objects.get_or_create(
            name="default",
            defaults={
                "host": "localhost",
                "port": 9876,
                "database_name": "email_security",
                "username": "admin",
                "password": "securepass123",
                "connection_timeout": 30,
                "max_connections": 10,
                "is_active": True,
                "is_default": True,
            },
        )

        if created:
            self.stdout.write(
                f"  ✓ Created default database config: {default_config.name}"
            )
        else:
            self.stdout.write(
                f"  - Database config already exists: {default_config.name}"
            )

    def create_sentiment_configs(self):
        """Create default sentiment configurations."""
        self.stdout.write("Creating sentiment configurations...")

        # Default weighted average configuration
        default_config, created = SentimentConfig.objects.get_or_create(
            name="default_weighted",
            defaults={
                "default_algorithm": "weighted_average",
                "default_window_hours": 24,
                "time_decay_factor": 0.9,
                "trend_weight": 0.2,
                "min_reports_for_confidence": 10,
                "enable_industry_normalization": True,
                "is_active": True,
                "is_default": True,
            },
        )

        if created:
            self.stdout.write(
                f"  ✓ Created default sentiment config: {default_config.name}"
            )
        else:
            self.stdout.write(
                f"  - Sentiment config already exists: {default_config.name}"
            )

        # Simple ratio configuration for comparison
        simple_config, created = SentimentConfig.objects.get_or_create(
            name="simple_ratio",
            defaults={
                "default_algorithm": "simple_ratio",
                "default_window_hours": 24,
                "time_decay_factor": 1.0,
                "trend_weight": 0.0,
                "min_reports_for_confidence": 5,
                "enable_industry_normalization": False,
                "is_active": True,
                "is_default": False,
            },
        )

        if created:
            self.stdout.write(f"  ✓ Created simple ratio config: {simple_config.name}")

    def create_job_configs(self):
        """Create default job configurations."""
        self.stdout.write("Creating job configurations...")

        # Default job configuration
        default_config, created = JobConfig.objects.get_or_create(
            name="default",
            defaults={
                "sync_interval_minutes": 60,
                "sync_batch_size": 1000,
                "sentiment_delay_minutes": 5,
                "segment_delay_minutes": 10,
                "overall_delay_minutes": 15,
                "max_retries": 3,
                "retry_delay_minutes": 5,
                "cleanup_old_jobs_days": 30,
                "is_active": True,
                "is_default": True,
            },
        )

        if created:
            self.stdout.write(f"  ✓ Created default job config: {default_config.name}")
        else:
            self.stdout.write(f"  - Job config already exists: {default_config.name}")

        # Development configuration (more frequent)
        dev_config, created = JobConfig.objects.get_or_create(
            name="development",
            defaults={
                "sync_interval_minutes": 15,
                "sync_batch_size": 500,
                "sentiment_delay_minutes": 2,
                "segment_delay_minutes": 3,
                "overall_delay_minutes": 5,
                "max_retries": 2,
                "retry_delay_minutes": 2,
                "cleanup_old_jobs_days": 7,
                "is_active": True,
                "is_default": False,
            },
        )

        if created:
            self.stdout.write(f"  ✓ Created development job config: {dev_config.name}")

    def create_industry_baselines(self):
        """Create industry baseline configurations."""
        self.stdout.write("Creating industry baselines...")

        # Industry baselines with realistic values
        baselines = [
            {
                "industry": "Technology",
                "baseline_sentiment": 0.65,
                "fn_fp_ratio_baseline": 1.2,
                "volatility_factor": 1.3,
                "description": "Technology companies typically have higher sentiment expectations",
            },
            {
                "industry": "Healthcare",
                "baseline_sentiment": 0.70,
                "fn_fp_ratio_baseline": 0.8,
                "volatility_factor": 0.9,
                "description": "Healthcare industry with high reliability requirements",
            },
            {
                "industry": "Finance",
                "baseline_sentiment": 0.75,
                "fn_fp_ratio_baseline": 0.6,
                "volatility_factor": 0.8,
                "description": "Financial services with strict security requirements",
            },
            {
                "industry": "E-commerce",
                "baseline_sentiment": 0.60,
                "fn_fp_ratio_baseline": 1.5,
                "volatility_factor": 1.4,
                "description": "E-commerce with high volume and variable quality",
            },
            {
                "industry": "Manufacturing",
                "baseline_sentiment": 0.68,
                "fn_fp_ratio_baseline": 1.0,
                "volatility_factor": 1.0,
                "description": "Manufacturing industry baseline",
            },
        ]

        for baseline_data in baselines:
            baseline, created = IndustryBaseline.objects.get_or_create(
                industry=baseline_data["industry"], defaults=baseline_data
            )

            if created:
                self.stdout.write(f"  ✓ Created baseline for {baseline.industry}")
            else:
                self.stdout.write(
                    f"  - Baseline already exists for {baseline.industry}"
                )
