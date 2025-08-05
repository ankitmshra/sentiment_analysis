"""
GraphQL schema for the sentiment analysis API.

This module defines GraphQL types and queries for accessing sentiment data
with real-time querying capabilities for dashboard visualization.
"""

import graphene
from graphene import relay, ObjectType, Field, List, String, Float, Int, DateTime
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Count, Sum

from .models import (
    Customer,
    SyncJob,
    SentimentScore,
    SegmentSentiment,
    OverallSentiment,
    IndustryBaseline,
)


# GraphQL Types
class CustomerType(DjangoObjectType):
    """GraphQL type for Customer model."""

    latest_sentiment_score = Float()
    total_reports_count = Int()
    sentiment_trend = String()

    class Meta:
        model = Customer
        fields = "__all__"
        filter_fields = {
            "company_name": ["exact", "icontains"],
            "industry": ["exact"],
            "is_active": ["exact"],
        }
        interfaces = (relay.Node,)

    def resolve_latest_sentiment_score(self, info):
        """Get the most recent sentiment score for this customer."""
        latest_score = (
            SentimentScore.objects.filter(customer=self).order_by("-created_at").first()
        )
        return latest_score.sentiment_score if latest_score else None

    def resolve_total_reports_count(self, info):
        """Get total FN/FP reports for this customer in the last 30 days."""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        sync_jobs = SyncJob.objects.filter(
            customer=self, status="completed", window_start__gte=thirty_days_ago
        )
        return sum(job.fn_count + job.fp_count for job in sync_jobs)

    def resolve_sentiment_trend(self, info):
        """Get sentiment trend direction for this customer."""
        recent_scores = SentimentScore.objects.filter(customer=self).order_by(
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


class SyncJobType(DjangoObjectType):
    """GraphQL type for SyncJob model."""

    duration_minutes = Float()

    class Meta:
        model = SyncJob
        fields = "__all__"
        filter_fields = {
            "customer": ["exact"],
            "status": ["exact"],
            "window_start": ["gte", "lte"],
        }
        interfaces = (relay.Node,)

    def resolve_duration_minutes(self, info):
        """Calculate job duration in minutes."""
        if self.started_at and self.completed_at:
            duration = self.completed_at - self.started_at
            return round(duration.total_seconds() / 60, 2)
        return None


class SentimentScoreType(DjangoObjectType):
    """GraphQL type for SentimentScore model."""

    class Meta:
        model = SentimentScore
        fields = "__all__"
        filter_fields = {
            "customer": ["exact"],
            "sentiment_score": ["gte", "lte"],
            "algorithm_used": ["exact"],
            "trend_direction": ["exact"],
            "created_at": ["gte", "lte"],
        }
        interfaces = (relay.Node,)


class SegmentSentimentType(DjangoObjectType):
    """GraphQL type for SegmentSentiment model."""

    class Meta:
        model = SegmentSentiment
        fields = "__all__"
        filter_fields = {
            "segment": ["exact", "icontains"],
            "average_sentiment": ["gte", "lte"],
            "trend_direction": ["exact"],
            "created_at": ["gte", "lte"],
        }
        interfaces = (relay.Node,)


class OverallSentimentType(DjangoObjectType):
    """GraphQL type for OverallSentiment model."""

    class Meta:
        model = OverallSentiment
        fields = "__all__"
        filter_fields = {
            "overall_sentiment": ["gte", "lte"],
            "trend_direction": ["exact"],
            "created_at": ["gte", "lte"],
        }
        interfaces = (relay.Node,)


class IndustryBaselineType(DjangoObjectType):
    """GraphQL type for IndustryBaseline model."""

    class Meta:
        model = IndustryBaseline
        fields = "__all__"
        filter_fields = {
            "industry": ["exact"],
            "is_active": ["exact"],
        }
        interfaces = (relay.Node,)


# Custom Types for Dashboard
class SentimentTrendType(ObjectType):
    """Custom type for sentiment trend data."""

    timestamp = DateTime()
    sentiment_score = Float()
    customer_count = Int()
    total_reports = Int()
    trend_direction = String()


class SegmentComparisonType(ObjectType):
    """Custom type for segment comparison data."""

    segment = String()
    sentiment = Float()
    customers = Int()
    trend = String()
    fn_count = Int()
    fp_count = Int()


class DashboardSummaryType(ObjectType):
    """Custom type for dashboard summary data."""

    overall_sentiment = Float()
    total_customers = Int()
    total_reports_today = Int()
    sentiment_trend = String()
    top_performing_segment = String()
    lowest_performing_segment = String()

    # Segment breakdown
    segment_breakdown = List(SegmentComparisonType)

    # Time series data
    hourly_sentiment = List(SentimentTrendType)


# Query Class
class Query(ObjectType):
    """Root Query for GraphQL API."""

    # Node fields for Relay
    node = relay.Node.Field()

    # Customer queries
    customer = relay.Node.Field(CustomerType)
    all_customers = DjangoFilterConnectionField(CustomerType)
    customers_by_industry = List(CustomerType, industry=String(required=True))
    customers_by_sentiment_range = List(
        CustomerType, min_sentiment=Float(), max_sentiment=Float()
    )

    # Sentiment score queries
    sentiment_score = relay.Node.Field(SentimentScoreType)
    all_sentiment_scores = DjangoFilterConnectionField(SentimentScoreType)
    customer_sentiment_history = List(
        SentimentScoreType, customer_id=Int(required=True), hours=Int(default_value=24)
    )
    sentiment_trends = List(SentimentTrendType, hours=Int(default_value=24))

    # Segment queries
    segment_sentiment = relay.Node.Field(SegmentSentimentType)
    all_segment_sentiments = DjangoFilterConnectionField(SegmentSentimentType)
    latest_segment_comparison = List(SegmentComparisonType)

    # Overall sentiment queries
    overall_sentiment = relay.Node.Field(OverallSentimentType)
    all_overall_sentiments = DjangoFilterConnectionField(OverallSentimentType)
    latest_overall_sentiment = Field(OverallSentimentType)

    # Dashboard query
    dashboard_summary = Field(DashboardSummaryType)

    # Sync job queries
    sync_job = relay.Node.Field(SyncJobType)
    all_sync_jobs = DjangoFilterConnectionField(SyncJobType)
    recent_sync_jobs = List(SyncJobType, limit=Int(default_value=10))

    # Industry baseline queries
    industry_baseline = relay.Node.Field(IndustryBaselineType)
    all_industry_baselines = DjangoFilterConnectionField(IndustryBaselineType)

    # Resolvers
    def resolve_customers_by_industry(self, info, industry):
        """Get customers filtered by industry."""
        return Customer.objects.filter(industry=industry, is_active=True)

    def resolve_customers_by_sentiment_range(
        self, info, min_sentiment=None, max_sentiment=None
    ):
        """Get customers filtered by sentiment range."""
        # Get customers with recent sentiment scores
        recent_scores = SentimentScore.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        )

        if min_sentiment is not None:
            recent_scores = recent_scores.filter(sentiment_score__gte=min_sentiment)
        if max_sentiment is not None:
            recent_scores = recent_scores.filter(sentiment_score__lte=max_sentiment)

        customer_ids = recent_scores.values_list("customer_id", flat=True).distinct()
        return Customer.objects.filter(id__in=customer_ids, is_active=True)

    def resolve_customer_sentiment_history(self, info, customer_id, hours):
        """Get sentiment history for a specific customer."""
        start_time = timezone.now() - timedelta(hours=hours)
        return SentimentScore.objects.filter(
            customer_id=customer_id, created_at__gte=start_time
        ).order_by("-created_at")

    def resolve_sentiment_trends(self, info, hours):
        """Get sentiment trends over time."""
        start_time = timezone.now() - timedelta(hours=hours)

        # Get sentiment scores grouped by hour
        scores = (
            SentimentScore.objects.filter(created_at__gte=start_time)
            .extra({"hour": "date_trunc('hour', created_at)"})
            .values("hour")
            .annotate(
                avg_sentiment=Avg("sentiment_score"),
                customer_count=Count("customer", distinct=True),
                total_reports=Sum("fn_count_used") + Sum("fp_count_used"),
            )
            .order_by("hour")
        )

        # Format response
        trend_data = []
        for score in scores:
            trend_data.append(
                SentimentTrendType(
                    timestamp=score["hour"],
                    sentiment_score=round(score["avg_sentiment"], 3),
                    customer_count=score["customer_count"],
                    total_reports=score["total_reports"] or 0,
                    trend_direction="stable",  # Could be calculated based on previous hour
                )
            )

        return trend_data

    def resolve_latest_segment_comparison(self, info):
        """Get latest segment comparison data."""
        # Get latest segment data
        latest_segments = (
            SegmentSentiment.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=2)
            )
            .order_by("segment", "-created_at")
            .distinct("segment")
        )

        comparison_data = []
        for segment in latest_segments:
            comparison_data.append(
                SegmentComparisonType(
                    segment=segment.segment,
                    sentiment=segment.average_sentiment,
                    customers=segment.total_customers,
                    trend=segment.trend_direction,
                    fn_count=segment.total_fn_count,
                    fp_count=segment.total_fp_count,
                )
            )

        return comparison_data

    def resolve_latest_overall_sentiment(self, info):
        """Get the latest overall sentiment data."""
        return OverallSentiment.objects.order_by("-created_at").first()

    def resolve_dashboard_summary(self, info):
        """Get comprehensive dashboard summary data."""
        # Get latest overall sentiment
        latest_overall = OverallSentiment.objects.order_by("-created_at").first()

        if not latest_overall:
            return None

        # Get today's report count
        today = timezone.now().date()
        today_jobs = SyncJob.objects.filter(
            status="completed", window_start__date=today
        )
        total_reports_today = sum(job.fn_count + job.fp_count for job in today_jobs)

        # Get recent segment data
        recent_segments = (
            SegmentSentiment.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=2)
            )
            .order_by("segment", "-created_at")
            .distinct("segment")
        )

        segment_breakdown = []
        for segment in recent_segments:
            segment_breakdown.append(
                SegmentComparisonType(
                    segment=segment.segment,
                    sentiment=segment.average_sentiment,
                    customers=segment.total_customers,
                    trend=segment.trend_direction,
                    fn_count=segment.total_fn_count,
                    fp_count=segment.total_fp_count,
                )
            )

        # Get hourly sentiment for last 24 hours
        hourly_scores = (
            SentimentScore.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            )
            .extra({"hour": "date_trunc('hour', created_at)"})
            .values("hour")
            .annotate(
                avg_sentiment=Avg("sentiment_score"),
                customer_count=Count("customer", distinct=True),
                total_reports=Sum("fn_count_used") + Sum("fp_count_used"),
            )
            .order_by("hour")
        )

        hourly_sentiment = []
        for score in hourly_scores:
            hourly_sentiment.append(
                SentimentTrendType(
                    timestamp=score["hour"],
                    sentiment_score=round(score["avg_sentiment"], 3),
                    customer_count=score["customer_count"],
                    total_reports=score["total_reports"] or 0,
                    trend_direction="stable",
                )
            )

        return DashboardSummaryType(
            overall_sentiment=latest_overall.overall_sentiment,
            total_customers=latest_overall.total_customers,
            total_reports_today=total_reports_today,
            sentiment_trend=latest_overall.trend_direction,
            top_performing_segment=latest_overall.top_performing_segment,
            lowest_performing_segment=latest_overall.lowest_performing_segment,
            segment_breakdown=segment_breakdown,
            hourly_sentiment=hourly_sentiment,
        )

    def resolve_recent_sync_jobs(self, info, limit):
        """Get recent sync jobs."""
        return SyncJob.objects.order_by("-created_at")[:limit]


# Create the schema
schema = graphene.Schema(query=Query)
