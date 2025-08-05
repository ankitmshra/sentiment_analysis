"""
Django REST Framework serializers for the sentiment analysis API.

This module contains serializers for all models to provide JSON API endpoints
with proper validation, filtering, and data transformation.
"""

from rest_framework import serializers
from django.utils import timezone
from datetime import datetime, timedelta
from .models import (
    Customer,
    SyncJob,
    SentimentScore,
    SegmentSentiment,
    OverallSentiment,
    IndustryBaseline,
)


class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for Customer model with computed fields."""

    # Computed fields
    latest_sentiment = serializers.SerializerMethodField()
    total_reports = serializers.SerializerMethodField()
    sentiment_trend = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "customer_id",
            "company_name",
            "industry",
            "contact_person",
            "phone",
            "address",
            "city",
            "state",
            "country",
            "postal_code",
            "created_at",
            "updated_at",
            "synced_at",
            "is_active",
            # Computed fields
            "latest_sentiment",
            "total_reports",
            "sentiment_trend",
        ]
        read_only_fields = [
            "id",
            "synced_at",
            "latest_sentiment",
            "total_reports",
            "sentiment_trend",
        ]

    def get_latest_sentiment(self, obj):
        """Get the most recent sentiment score for this customer."""
        latest_score = (
            SentimentScore.objects.filter(customer=obj).order_by("-created_at").first()
        )
        if latest_score:
            return {
                "score": latest_score.sentiment_score,
                "label": latest_score.sentiment_label,
                "confidence": latest_score.confidence_score,
                "created_at": latest_score.created_at,
            }
        return None

    def get_total_reports(self, obj):
        """Get total FN/FP reports for this customer in the last 30 days."""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        sync_jobs = SyncJob.objects.filter(
            customer=obj, status="completed", window_start__gte=thirty_days_ago
        )

        total_fn = sum(job.fn_count for job in sync_jobs)
        total_fp = sum(job.fp_count for job in sync_jobs)

        return {
            "fn_count": total_fn,
            "fp_count": total_fp,
            "total": total_fn + total_fp,
        }

    def get_sentiment_trend(self, obj):
        """Get sentiment trend direction for this customer."""
        recent_scores = SentimentScore.objects.filter(customer=obj).order_by(
            "-created_at"
        )[:3]

        if len(recent_scores) < 2:
            return "stable"

        scores = [score.sentiment_score for score in recent_scores]

        if scores[0] > scores[1] * 1.05:  # 5% improvement
            return "improving"
        elif scores[0] < scores[1] * 0.95:  # 5% decline
            return "declining"
        else:
            return "stable"


class SyncJobSerializer(serializers.ModelSerializer):
    """Serializer for SyncJob model."""

    customer_name = serializers.CharField(
        source="customer.company_name", read_only=True
    )
    customer_industry = serializers.CharField(
        source="customer.industry", read_only=True
    )
    total_reports = serializers.ReadOnlyField()
    duration_minutes = serializers.SerializerMethodField()

    class Meta:
        model = SyncJob
        fields = [
            "id",
            "job_id",
            "customer",
            "customer_name",
            "customer_industry",
            "window_start",
            "window_end",
            "fn_count",
            "fp_count",
            "total_reports",
            "status",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
            "duration_minutes",
        ]
        read_only_fields = ["id", "job_id", "total_reports", "duration_minutes"]

    def get_duration_minutes(self, obj):
        """Calculate job duration in minutes."""
        if obj.started_at and obj.completed_at:
            duration = obj.completed_at - obj.started_at
            return round(duration.total_seconds() / 60, 2)
        return None


class SentimentScoreSerializer(serializers.ModelSerializer):
    """Serializer for SentimentScore model."""

    customer_name = serializers.CharField(
        source="customer.company_name", read_only=True
    )
    customer_industry = serializers.CharField(
        source="customer.industry", read_only=True
    )
    sentiment_label = serializers.ReadOnlyField()
    total_reports_used = serializers.ReadOnlyField()

    class Meta:
        model = SentimentScore
        fields = [
            "id",
            "job_id",
            "customer",
            "customer_name",
            "customer_industry",
            "sentiment_score",
            "sentiment_label",
            "algorithm_used",
            "calculation_window_hours",
            "fn_count_used",
            "fp_count_used",
            "total_reports_used",
            "trend_direction",
            "confidence_score",
            "created_at",
        ]
        read_only_fields = ["id", "job_id", "sentiment_label", "total_reports_used"]


class SegmentSentimentSerializer(serializers.ModelSerializer):
    """Serializer for SegmentSentiment model."""

    sentiment_label = serializers.ReadOnlyField()
    total_reports = serializers.ReadOnlyField()

    class Meta:
        model = SegmentSentiment
        fields = [
            "id",
            "job_id",
            "segment",
            "total_customers",
            "total_fn_count",
            "total_fp_count",
            "total_reports",
            "average_sentiment",
            "median_sentiment",
            "sentiment_std_dev",
            "sentiment_label",
            "trend_direction",
            "calculation_window_hours",
            "created_at",
        ]
        read_only_fields = ["id", "job_id", "sentiment_label", "total_reports"]


class OverallSentimentSerializer(serializers.ModelSerializer):
    """Serializer for OverallSentiment model."""

    sentiment_label = serializers.ReadOnlyField()
    total_reports = serializers.ReadOnlyField()

    class Meta:
        model = OverallSentiment
        fields = [
            "id",
            "job_id",
            "total_customers",
            "total_fn_count",
            "total_fp_count",
            "total_reports",
            "overall_sentiment",
            "weighted_sentiment",
            "sentiment_variance",
            "sentiment_label",
            "trend_direction",
            "top_performing_segment",
            "lowest_performing_segment",
            "calculation_window_hours",
            "created_at",
        ]
        read_only_fields = ["id", "job_id", "sentiment_label", "total_reports"]


class IndustryBaselineSerializer(serializers.ModelSerializer):
    """Serializer for IndustryBaseline model."""

    class Meta:
        model = IndustryBaseline
        fields = [
            "id",
            "industry",
            "baseline_sentiment",
            "fn_fp_ratio_baseline",
            "volatility_factor",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# Time-range filtering serializers
class TimeRangeSerializer(serializers.Serializer):
    """Serializer for time range filtering."""

    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    hours = serializers.IntegerField(
        required=False, min_value=1, max_value=8760
    )  # Max 1 year

    def validate(self, data):
        """Validate time range parameters."""
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        hours = data.get("hours")

        # If no parameters provided, default to last 24 hours
        if not any([start_date, end_date, hours]):
            data["hours"] = 24
            return data

        # If hours is provided, ignore start/end dates
        if hours:
            data["end_date"] = timezone.now()
            data["start_date"] = data["end_date"] - timedelta(hours=hours)
            return data

        # If start_date provided without end_date, default end to now
        if start_date and not end_date:
            data["end_date"] = timezone.now()

        # If end_date provided without start_date, default to 24 hours before end
        if end_date and not start_date:
            data["start_date"] = end_date - timedelta(hours=24)

        # Validate date range
        if data["start_date"] >= data["end_date"]:
            raise serializers.ValidationError("start_date must be before end_date")

        # Validate range is not too large (max 1 year)
        if (data["end_date"] - data["start_date"]).days > 365:
            raise serializers.ValidationError("Date range cannot exceed 1 year")

        return data


class SentimentTrendSerializer(serializers.Serializer):
    """Serializer for sentiment trend data."""

    timestamp = serializers.DateTimeField()
    sentiment_score = serializers.FloatField()
    customer_count = serializers.IntegerField()
    total_reports = serializers.IntegerField()
    trend_direction = serializers.CharField()


class DashboardSummarySerializer(serializers.Serializer):
    """Serializer for dashboard summary data."""

    overall_sentiment = serializers.FloatField()
    total_customers = serializers.IntegerField()
    total_reports_today = serializers.IntegerField()
    sentiment_trend = serializers.CharField()
    top_performing_segment = serializers.CharField()
    lowest_performing_segment = serializers.CharField()
    recent_alerts = serializers.ListField(child=serializers.DictField())

    # Segment breakdown
    segment_breakdown = serializers.ListField(child=serializers.DictField())

    # Time series data for charts
    hourly_sentiment = serializers.ListField(child=SentimentTrendSerializer())
