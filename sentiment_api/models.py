"""
Database models for the sentiment analysis API.

This module contains all the models for storing customer data, sentiment scores,
sync jobs, and related information for the sentiment analysis system.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid


class Customer(models.Model):
    """
    Model representing customers from the external database.
    This is a local copy for caching and reference purposes.
    """

    customer_id = models.IntegerField(
        unique=True, help_text="Customer ID from external database"
    )
    company_name = models.CharField(max_length=255, help_text="Company name")
    industry = models.CharField(max_length=100, help_text="Industry sector")
    contact_person = models.CharField(
        max_length=255, help_text="Name of contact person"
    )
    phone = models.CharField(
        max_length=20, blank=True, null=True, help_text="Phone number"
    )
    address = models.TextField(blank=True, null=True, help_text="Company address")
    city = models.CharField(max_length=100, blank=True, null=True, help_text="City")
    state = models.CharField(
        max_length=100, blank=True, null=True, help_text="State/Province"
    )
    country = models.CharField(
        max_length=100, blank=True, null=True, help_text="Country"
    )
    postal_code = models.CharField(
        max_length=20, blank=True, null=True, help_text="Postal code"
    )
    created_at = models.DateTimeField(
        help_text="When customer was created in external DB"
    )
    updated_at = models.DateTimeField(
        help_text="When customer was last updated in external DB"
    )

    # Local tracking fields
    synced_at = models.DateTimeField(
        auto_now=True, help_text="When this record was last synced"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether customer is active"
    )

    class Meta:
        db_table = "customers"
        indexes = [
            models.Index(fields=["customer_id"]),
            models.Index(fields=["industry"]),
            models.Index(fields=["company_name"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["company_name"]

    def __str__(self):
        return f"{self.company_name} ({self.customer_id})"


class SyncJob(models.Model):
    """
    Model for tracking hourly sync jobs that extract FN/FP counts from external database.
    Each job processes one hour window of data for all customers.
    """

    JOB_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    job_id = models.UUIDField(
        default=uuid.uuid4, unique=True, help_text="Unique job identifier"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, help_text="Customer this job is for"
    )
    window_start = models.DateTimeField(
        help_text="Start of the 1-hour window being processed"
    )
    window_end = models.DateTimeField(
        help_text="End of the 1-hour window being processed"
    )
    fn_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="False Negative count for this window",
    )
    fp_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="False Positive count for this window",
    )
    status = models.CharField(
        max_length=20,
        choices=JOB_STATUS_CHOICES,
        default="pending",
        help_text="Job status",
    )
    error_message = models.TextField(
        blank=True, null=True, help_text="Error message if job failed"
    )
    started_at = models.DateTimeField(
        blank=True, null=True, help_text="When job started processing"
    )
    completed_at = models.DateTimeField(
        blank=True, null=True, help_text="When job completed"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When job was created"
    )

    class Meta:
        db_table = "sync_jobs"
        indexes = [
            models.Index(fields=["customer", "window_start"]),
            models.Index(fields=["status"]),
            models.Index(fields=["window_start", "window_end"]),
            models.Index(fields=["created_at"]),
        ]
        unique_together = ["customer", "window_start", "window_end"]
        ordering = ["-window_start"]

    def __str__(self):
        return f"SyncJob {self.job_id} - {self.customer.company_name} ({self.window_start})"

    @property
    def total_reports(self):
        """Total FN + FP reports for this window."""
        return self.fn_count + self.fp_count

    def mark_as_running(self):
        """Mark job as running."""
        self.status = "running"
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def mark_as_completed(self, fn_count, fp_count):
        """Mark job as completed with counts."""
        self.status = "completed"
        self.fn_count = fn_count
        self.fp_count = fp_count
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "fn_count", "fp_count", "completed_at"])

    def mark_as_failed(self, error_message):
        """Mark job as failed with error message."""
        self.status = "failed"
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "error_message", "completed_at"])


class SentimentScore(models.Model):
    """
    Model for storing calculated sentiment scores for customers.
    Each record represents a customer's sentiment at a specific point in time.
    """

    job_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text="Unique identifier for this sentiment calculation",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        help_text="Customer this sentiment score is for",
    )
    sentiment_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Sentiment score between 0.0 (very negative) and 1.0 (very positive)",
    )
    algorithm_used = models.CharField(
        max_length=50, help_text="Algorithm used for calculation"
    )
    calculation_window_hours = models.IntegerField(
        default=24, help_text="Hours of data used in calculation"
    )
    fn_count_used = models.IntegerField(help_text="Total FN count used in calculation")
    fp_count_used = models.IntegerField(help_text="Total FP count used in calculation")
    trend_direction = models.CharField(
        max_length=20,
        choices=[
            ("improving", "Improving"),
            ("declining", "Declining"),
            ("stable", "Stable"),
        ],
        help_text="Trend direction compared to previous calculation",
    )
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence in this sentiment score (0.0 = low, 1.0 = high)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When this sentiment was calculated"
    )

    class Meta:
        db_table = "sentiment_scores"
        indexes = [
            models.Index(fields=["customer", "created_at"]),
            models.Index(fields=["sentiment_score"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["algorithm_used"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Sentiment {self.sentiment_score:.3f} - {self.customer.company_name} ({self.created_at})"

    @property
    def total_reports_used(self):
        """Total reports used in this calculation."""
        return self.fn_count_used + self.fp_count_used

    @property
    def sentiment_label(self):
        """Human-readable sentiment label."""
        if self.sentiment_score >= 0.8:
            return "Very Positive"
        elif self.sentiment_score >= 0.6:
            return "Positive"
        elif self.sentiment_score >= 0.4:
            return "Neutral"
        elif self.sentiment_score >= 0.2:
            return "Negative"
        else:
            return "Very Negative"


class SegmentSentiment(models.Model):
    """
    Model for storing industry segment sentiment analysis.
    Aggregates sentiment across all customers in an industry.
    """

    job_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text="Unique identifier for this segment analysis",
    )
    segment = models.CharField(max_length=100, help_text="Industry segment name")
    total_customers = models.IntegerField(
        help_text="Number of customers in this segment"
    )
    total_fn_count = models.IntegerField(help_text="Total FN reports for this segment")
    total_fp_count = models.IntegerField(help_text="Total FP reports for this segment")
    average_sentiment = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Average sentiment score for this segment",
    )
    median_sentiment = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Median sentiment score for this segment",
    )
    sentiment_std_dev = models.FloatField(
        help_text="Standard deviation of sentiment scores"
    )
    trend_direction = models.CharField(
        max_length=20,
        choices=[
            ("improving", "Improving"),
            ("declining", "Declining"),
            ("stable", "Stable"),
        ],
        help_text="Trend direction for this segment",
    )
    calculation_window_hours = models.IntegerField(
        default=24, help_text="Hours of data used in calculation"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When this analysis was performed"
    )

    class Meta:
        db_table = "segment_sentiment"
        indexes = [
            models.Index(fields=["segment", "created_at"]),
            models.Index(fields=["average_sentiment"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at", "segment"]

    def __str__(self):
        return f"Segment {self.segment} - Avg: {self.average_sentiment:.3f} ({self.created_at})"

    @property
    def total_reports(self):
        """Total reports for this segment."""
        return self.total_fn_count + self.total_fp_count

    @property
    def sentiment_label(self):
        """Human-readable sentiment label for the segment."""
        if self.average_sentiment >= 0.8:
            return "Very Positive"
        elif self.average_sentiment >= 0.6:
            return "Positive"
        elif self.average_sentiment >= 0.4:
            return "Neutral"
        elif self.average_sentiment >= 0.2:
            return "Negative"
        else:
            return "Very Negative"


class OverallSentiment(models.Model):
    """
    Model for storing overall product sentiment across all customers.
    Represents the global sentiment state of the product.
    """

    job_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text="Unique identifier for this overall analysis",
    )
    total_customers = models.IntegerField(help_text="Total number of active customers")
    total_fn_count = models.IntegerField(
        help_text="Total FN reports across all customers"
    )
    total_fp_count = models.IntegerField(
        help_text="Total FP reports across all customers"
    )
    overall_sentiment = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Overall sentiment score across all customers",
    )
    weighted_sentiment = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Sentiment weighted by customer activity/importance",
    )
    sentiment_variance = models.FloatField(
        help_text="Variance in sentiment across customers"
    )
    trend_direction = models.CharField(
        max_length=20,
        choices=[
            ("improving", "Improving"),
            ("declining", "Declining"),
            ("stable", "Stable"),
        ],
        help_text="Overall trend direction",
    )
    top_performing_segment = models.CharField(
        max_length=100, help_text="Industry segment with highest sentiment"
    )
    lowest_performing_segment = models.CharField(
        max_length=100, help_text="Industry segment with lowest sentiment"
    )
    calculation_window_hours = models.IntegerField(
        default=24, help_text="Hours of data used in calculation"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When this analysis was performed"
    )

    class Meta:
        db_table = "overall_sentiment"
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["overall_sentiment"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Overall Sentiment {self.overall_sentiment:.3f} ({self.created_at})"

    @property
    def total_reports(self):
        """Total reports across all customers."""
        return self.total_fn_count + self.total_fp_count

    @property
    def sentiment_label(self):
        """Human-readable sentiment label."""
        if self.overall_sentiment >= 0.8:
            return "Very Positive"
        elif self.overall_sentiment >= 0.6:
            return "Positive"
        elif self.overall_sentiment >= 0.4:
            return "Neutral"
        elif self.overall_sentiment >= 0.2:
            return "Negative"
        else:
            return "Very Negative"


class IndustryBaseline(models.Model):
    """
    Model for storing industry-specific sentiment baselines.
    Used for normalizing sentiment scores relative to industry standards.
    Admin-configurable reference values.
    """

    industry = models.CharField(max_length=100, unique=True, help_text="Industry name")
    baseline_sentiment = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Expected baseline sentiment for this industry",
    )
    fn_fp_ratio_baseline = models.FloatField(
        help_text="Expected FN/FP ratio for this industry"
    )
    volatility_factor = models.FloatField(
        default=1.0,
        help_text="Industry volatility factor (higher = more volatile sentiment)",
    )
    description = models.TextField(
        blank=True, help_text="Description of this industry baseline"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this baseline is active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "industry_baselines"
        indexes = [
            models.Index(fields=["industry"]),
            models.Index(fields=["is_active"]),
        ]
        ordering = ["industry"]

    def __str__(self):
        return f"{self.industry} - Baseline: {self.baseline_sentiment:.3f}"
