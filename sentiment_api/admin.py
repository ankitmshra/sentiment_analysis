"""
Django admin configuration for sentiment analysis models.

This module configures the Django admin interface for managing
customers, sentiment scores, sync jobs, and related data.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Customer,
    SyncJob,
    SentimentScore,
    SegmentSentiment,
    OverallSentiment,
    IndustryBaseline,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Admin configuration for Customer model."""

    list_display = [
        "customer_id",
        "company_name",
        "industry",
        "contact_person",
        "city",
        "country",
        "is_active",
        "synced_at",
    ]
    list_filter = [
        "industry",
        "is_active",
        "country",
        "state",
        "created_at",
        "synced_at",
    ]
    search_fields = [
        "company_name",
        "contact_person",
        "customer_id",
        "industry",
    ]
    readonly_fields = [
        "customer_id",
        "created_at",
        "updated_at",
        "synced_at",
    ]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "customer_id",
                    "company_name",
                    "industry",
                    "contact_person",
                    "phone",
                )
            },
        ),
        (
            "Address",
            {
                "fields": (
                    "address",
                    "city",
                    "state",
                    "country",
                    "postal_code",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                    "created_at",
                    "updated_at",
                    "synced_at",
                )
            },
        ),
    )
    ordering = ["company_name"]
    list_per_page = 50

    def get_queryset(self, request):
        """Optimize queryset for admin list view."""
        return super().get_queryset(request).select_related()


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    """Admin configuration for SyncJob model."""

    list_display = [
        "job_id_short",
        "customer_link",
        "window_period",
        "fn_count",
        "fp_count",
        "total_reports",
        "status_colored",
        "duration",
        "created_at",
    ]
    list_filter = [
        "status",
        "window_start",
        "created_at",
        "customer__industry",
    ]
    search_fields = [
        "job_id",
        "customer__company_name",
        "customer__customer_id",
    ]
    readonly_fields = [
        "job_id",
        "created_at",
        "started_at",
        "completed_at",
        "total_reports",
        "duration",
    ]
    fieldsets = (
        (
            "Job Information",
            {
                "fields": (
                    "job_id",
                    "customer",
                    "status",
                    "created_at",
                )
            },
        ),
        (
            "Time Window",
            {
                "fields": (
                    "window_start",
                    "window_end",
                    "started_at",
                    "completed_at",
                    "duration",
                )
            },
        ),
        (
            "Results",
            {
                "fields": (
                    "fn_count",
                    "fp_count",
                    "total_reports",
                    "error_message",
                )
            },
        ),
    )
    ordering = ["-created_at"]
    list_per_page = 100

    def job_id_short(self, obj):
        """Display shortened job ID."""
        return str(obj.job_id)[:8] + "..."

    job_id_short.short_description = "Job ID"

    def customer_link(self, obj):
        """Display customer as clickable link."""
        url = reverse("admin:sentiment_api_customer_change", args=[obj.customer.pk])
        return format_html('<a href="{}">{}</a>', url, obj.customer.company_name)

    customer_link.short_description = "Customer"

    def window_period(self, obj):
        """Display time window period."""
        return "{} - {}".format(
            obj.window_start.strftime("%H:%M"), obj.window_end.strftime("%H:%M")
        )

    window_period.short_description = "Window"

    def status_colored(self, obj):
        """Display status with color coding."""
        colors = {
            "pending": "orange",
            "running": "blue",
            "completed": "green",
            "failed": "red",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {};">{}</span>', color, obj.get_status_display()
        )

    status_colored.short_description = "Status"

    def duration(self, obj):
        """Calculate and display job duration."""
        if obj.started_at and obj.completed_at:
            duration = obj.completed_at - obj.started_at
            return "{:.1f}s".format(duration.total_seconds())
        return "-"

    duration.short_description = "Duration"

    def get_queryset(self, request):
        """Optimize queryset for admin list view."""
        return super().get_queryset(request).select_related("customer")


@admin.register(SentimentScore)
class SentimentScoreAdmin(admin.ModelAdmin):
    """Admin configuration for SentimentScore model."""

    list_display = [
        "customer_link",
        "sentiment_score_colored",
        "sentiment_label",
        "algorithm_used",
        "trend_direction_colored",
        "confidence_score",
        "total_reports_used",
        "created_at",
    ]
    list_filter = [
        "algorithm_used",
        "trend_direction",
        "created_at",
        "customer__industry",
        "calculation_window_hours",
    ]
    search_fields = [
        "customer__company_name",
        "customer__customer_id",
        "job_id",
    ]
    readonly_fields = [
        "job_id",
        "created_at",
        "total_reports_used",
        "sentiment_label",
    ]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "job_id",
                    "customer",
                    "created_at",
                )
            },
        ),
        (
            "Sentiment Analysis",
            {
                "fields": (
                    "sentiment_score",
                    "sentiment_label",
                    "algorithm_used",
                    "calculation_window_hours",
                    "confidence_score",
                )
            },
        ),
        (
            "Data Used",
            {
                "fields": (
                    "fn_count_used",
                    "fp_count_used",
                    "total_reports_used",
                )
            },
        ),
        ("Trend Analysis", {"fields": ("trend_direction",)}),
    )
    ordering = ["-created_at"]
    list_per_page = 100

    def customer_link(self, obj):
        """Display customer as clickable link."""
        url = reverse("admin:sentiment_api_customer_change", args=[obj.customer.pk])
        return format_html('<a href="{}">{}</a>', url, obj.customer.company_name)

    customer_link.short_description = "Customer"

    def sentiment_score_colored(self, obj):
        """Display sentiment score with color coding."""
        if obj.sentiment_score >= 0.8:
            color = "green"
        elif obj.sentiment_score >= 0.6:
            color = "lightgreen"
        elif obj.sentiment_score >= 0.4:
            color = "orange"
        elif obj.sentiment_score >= 0.2:
            color = "red"
        else:
            color = "darkred"

        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.3f}</span>',
            color,
            obj.sentiment_score,
        )

    sentiment_score_colored.short_description = "Score"

    def trend_direction_colored(self, obj):
        """Display trend direction with color coding."""
        colors = {
            "improving": "green",
            "stable": "orange",
            "declining": "red",
        }
        color = colors.get(obj.trend_direction, "black")
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_trend_direction_display(),
        )

    trend_direction_colored.short_description = "Trend"

    def get_queryset(self, request):
        """Optimize queryset for admin list view."""
        return super().get_queryset(request).select_related("customer")


@admin.register(SegmentSentiment)
class SegmentSentimentAdmin(admin.ModelAdmin):
    """Admin configuration for SegmentSentiment model."""

    list_display = [
        "segment",
        "total_customers",
        "average_sentiment_colored",
        "median_sentiment",
        "sentiment_std_dev",
        "trend_direction_colored",
        "total_reports",
        "created_at",
    ]
    list_filter = [
        "segment",
        "trend_direction",
        "created_at",
        "calculation_window_hours",
    ]
    search_fields = [
        "segment",
        "job_id",
    ]
    readonly_fields = [
        "job_id",
        "created_at",
        "total_reports",
        "sentiment_label",
    ]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "job_id",
                    "segment",
                    "created_at",
                    "calculation_window_hours",
                )
            },
        ),
        (
            "Customer Data",
            {
                "fields": (
                    "total_customers",
                    "total_fn_count",
                    "total_fp_count",
                    "total_reports",
                )
            },
        ),
        (
            "Sentiment Analysis",
            {
                "fields": (
                    "average_sentiment",
                    "median_sentiment",
                    "sentiment_std_dev",
                    "sentiment_label",
                    "trend_direction",
                )
            },
        ),
    )
    ordering = ["-created_at", "segment"]
    list_per_page = 50

    def average_sentiment_colored(self, obj):
        """Display average sentiment with color coding."""
        if obj.average_sentiment >= 0.8:
            color = "green"
        elif obj.average_sentiment >= 0.6:
            color = "lightgreen"
        elif obj.average_sentiment >= 0.4:
            color = "orange"
        elif obj.average_sentiment >= 0.2:
            color = "red"
        else:
            color = "darkred"

        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.3f}</span>',
            color,
            obj.average_sentiment,
        )

    average_sentiment_colored.short_description = "Avg Score"

    def trend_direction_colored(self, obj):
        """Display trend direction with color coding."""
        colors = {
            "improving": "green",
            "stable": "orange",
            "declining": "red",
        }
        color = colors.get(obj.trend_direction, "black")
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_trend_direction_display(),
        )

    trend_direction_colored.short_description = "Trend"


@admin.register(OverallSentiment)
class OverallSentimentAdmin(admin.ModelAdmin):
    """Admin configuration for OverallSentiment model."""

    list_display = [
        "overall_sentiment_colored",
        "weighted_sentiment",
        "total_customers",
        "total_reports",
        "trend_direction_colored",
        "top_performing_segment",
        "lowest_performing_segment",
        "created_at",
    ]
    list_filter = [
        "trend_direction",
        "created_at",
        "calculation_window_hours",
    ]
    search_fields = [
        "job_id",
        "top_performing_segment",
        "lowest_performing_segment",
    ]
    readonly_fields = [
        "job_id",
        "created_at",
        "total_reports",
        "sentiment_label",
    ]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "job_id",
                    "created_at",
                    "calculation_window_hours",
                )
            },
        ),
        (
            "Overall Data",
            {
                "fields": (
                    "total_customers",
                    "total_fn_count",
                    "total_fp_count",
                    "total_reports",
                )
            },
        ),
        (
            "Sentiment Analysis",
            {
                "fields": (
                    "overall_sentiment",
                    "weighted_sentiment",
                    "sentiment_variance",
                    "sentiment_label",
                    "trend_direction",
                )
            },
        ),
        (
            "Segment Performance",
            {
                "fields": (
                    "top_performing_segment",
                    "lowest_performing_segment",
                )
            },
        ),
    )
    ordering = ["-created_at"]
    list_per_page = 50

    def overall_sentiment_colored(self, obj):
        """Display overall sentiment with color coding."""
        if obj.overall_sentiment >= 0.8:
            color = "green"
        elif obj.overall_sentiment >= 0.6:
            color = "lightgreen"
        elif obj.overall_sentiment >= 0.4:
            color = "orange"
        elif obj.overall_sentiment >= 0.2:
            color = "red"
        else:
            color = "darkred"

        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.3f}</span>',
            color,
            obj.overall_sentiment,
        )

    overall_sentiment_colored.short_description = "Overall Score"

    def trend_direction_colored(self, obj):
        """Display trend direction with color coding."""
        colors = {
            "improving": "green",
            "stable": "orange",
            "declining": "red",
        }
        color = colors.get(obj.trend_direction, "black")
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_trend_direction_display(),
        )

    trend_direction_colored.short_description = "Trend"


@admin.register(IndustryBaseline)
class IndustryBaselineAdmin(admin.ModelAdmin):
    """Admin configuration for IndustryBaseline model."""

    list_display = [
        "industry",
        "baseline_sentiment_colored",
        "fn_fp_ratio_baseline",
        "volatility_factor",
        "is_active",
        "updated_at",
    ]
    list_filter = [
        "is_active",
        "created_at",
        "updated_at",
    ]
    search_fields = [
        "industry",
        "description",
    ]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "industry",
                    "description",
                    "is_active",
                )
            },
        ),
        (
            "Baseline Parameters",
            {
                "fields": (
                    "baseline_sentiment",
                    "fn_fp_ratio_baseline",
                    "volatility_factor",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["industry"]
    list_per_page = 50

    def baseline_sentiment_colored(self, obj):
        """Display baseline sentiment with color coding."""
        if obj.baseline_sentiment >= 0.8:
            color = "green"
        elif obj.baseline_sentiment >= 0.6:
            color = "lightgreen"
        elif obj.baseline_sentiment >= 0.4:
            color = "orange"
        elif obj.baseline_sentiment >= 0.2:
            color = "red"
        else:
            color = "darkred"

        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.3f}</span>',
            color,
            obj.baseline_sentiment,
        )

    baseline_sentiment_colored.short_description = "Baseline"
