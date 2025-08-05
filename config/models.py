"""
Configuration models for the sentiment analysis system.

This module contains models for storing system configuration,
including database connection settings that can be managed via Django admin.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class DatabaseConfig(models.Model):
    """
    Model for storing external database connection configuration.
    Admin-configurable settings for connecting to the source PostgreSQL database.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Configuration name (e.g., 'production', 'staging')",
    )
    host = models.CharField(max_length=255, help_text="Database host")
    port = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        default=5432,
        help_text="Database port",
    )
    database_name = models.CharField(max_length=100, help_text="Database name")
    username = models.CharField(max_length=100, help_text="Database username")
    password = models.CharField(max_length=255, help_text="Database password")

    # Connection settings
    connection_timeout = models.IntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(300)],
        help_text="Connection timeout in seconds",
    )
    max_connections = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Maximum number of connections",
    )

    # Status and metadata
    is_active = models.BooleanField(
        default=True, help_text="Whether this configuration is active"
    )
    is_default = models.BooleanField(
        default=False, help_text="Whether this is the default configuration"
    )
    last_tested = models.DateTimeField(
        blank=True, null=True, help_text="When this configuration was last tested"
    )
    test_status = models.CharField(
        max_length=20,
        choices=[
            ("success", "Success"),
            ("failed", "Failed"),
            ("pending", "Pending"),
            ("not_tested", "Not Tested"),
        ],
        default="not_tested",
        help_text="Status of last connection test",
    )
    test_error_message = models.TextField(
        blank=True, null=True, help_text="Error message from last failed test"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "database_configs"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["is_default"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.host}:{self.port}/{self.database_name})"

    def save(self, *args, **kwargs):
        """Ensure only one default configuration exists."""
        if self.is_default:
            # Set all other configs to non-default
            DatabaseConfig.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def get_connection_string(self):
        """Get PostgreSQL connection string."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database_name}"

    def mark_test_success(self):
        """Mark connection test as successful."""
        self.test_status = "success"
        self.last_tested = timezone.now()
        self.test_error_message = None
        self.save(update_fields=["test_status", "last_tested", "test_error_message"])

    def mark_test_failed(self, error_message):
        """Mark connection test as failed."""
        self.test_status = "failed"
        self.last_tested = timezone.now()
        self.test_error_message = error_message
        self.save(update_fields=["test_status", "last_tested", "test_error_message"])


class SentimentConfig(models.Model):
    """
    Model for storing sentiment calculation configuration.
    Admin-configurable parameters for sentiment algorithms.
    """

    name = models.CharField(max_length=100, unique=True, help_text="Configuration name")

    # Algorithm selection
    default_algorithm = models.CharField(
        max_length=50,
        choices=[
            ("simple_ratio", "Simple Ratio"),
            ("weighted_average", "Weighted Average"),
            ("trend_adjusted", "Trend Adjusted"),
            ("industry_normalized", "Industry Normalized"),
        ],
        default="weighted_average",
        help_text="Default sentiment calculation algorithm",
    )

    # Time window settings
    default_window_hours = models.IntegerField(
        default=24,
        validators=[MinValueValidator(1), MaxValueValidator(168)],  # Max 1 week
        help_text="Default calculation window in hours",
    )

    # Weighted average parameters
    time_decay_factor = models.FloatField(
        default=0.9,
        validators=[MinValueValidator(0.1), MaxValueValidator(1.0)],
        help_text="Time decay factor for weighted average (0.1-1.0)",
    )

    # Trend calculation parameters
    trend_weight = models.FloatField(
        default=0.2,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Weight given to trend in calculation (0.0-1.0)",
    )

    # Confidence scoring
    min_reports_for_confidence = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1)],
        help_text="Minimum reports needed for high confidence score",
    )

    # Industry normalization
    enable_industry_normalization = models.BooleanField(
        default=True, help_text="Whether to normalize scores against industry baselines"
    )

    # Status
    is_active = models.BooleanField(
        default=True, help_text="Whether this configuration is active"
    )
    is_default = models.BooleanField(
        default=False, help_text="Whether this is the default configuration"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sentiment_configs"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["is_default"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.default_algorithm})"

    def save(self, *args, **kwargs):
        """Ensure only one default configuration exists."""
        if self.is_default:
            # Set all other configs to non-default
            SentimentConfig.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class JobConfig(models.Model):
    """
    Model for storing background job configuration.
    Admin-configurable settings for job scheduling and execution.
    """

    name = models.CharField(max_length=100, unique=True, help_text="Configuration name")

    # Sync job settings
    sync_interval_minutes = models.IntegerField(
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(1440)],  # Max 24 hours
        help_text="Interval between sync jobs in minutes",
    )
    sync_batch_size = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
        help_text="Number of records to process per batch",
    )

    # Sentiment calculation settings
    sentiment_delay_minutes = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0), MaxValueValidator(60)],
        help_text="Delay after sync before sentiment calculation (minutes)",
    )

    # Segment analysis settings
    segment_delay_minutes = models.IntegerField(
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(60)],
        help_text="Delay after sentiment calc before segment analysis (minutes)",
    )

    # Overall analysis settings
    overall_delay_minutes = models.IntegerField(
        default=15,
        validators=[MinValueValidator(0), MaxValueValidator(60)],
        help_text="Delay after segment analysis before overall analysis (minutes)",
    )

    # Retry settings
    max_retries = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Maximum number of job retries",
    )
    retry_delay_minutes = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Delay between retries in minutes",
    )

    # Cleanup settings
    cleanup_old_jobs_days = models.IntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Days to keep old job records",
    )

    # Status
    is_active = models.BooleanField(
        default=True, help_text="Whether this configuration is active"
    )
    is_default = models.BooleanField(
        default=False, help_text="Whether this is the default configuration"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "job_configs"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["is_default"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (Sync: {self.sync_interval_minutes}min)"

    def save(self, *args, **kwargs):
        """Ensure only one default configuration exists."""
        if self.is_default:
            # Set all other configs to non-default
            JobConfig.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_active_config(cls):
        """Get the active job configuration."""
        try:
            return cls.objects.filter(is_active=True, is_default=True).first()
        except cls.DoesNotExist:
            # Return default configuration if no active default found
            return cls.objects.filter(is_active=True).first()
