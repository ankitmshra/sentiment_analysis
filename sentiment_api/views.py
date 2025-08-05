"""
Django REST Framework views for the sentiment analysis API.

This module contains all the API endpoints for accessing sentiment data,
customer information, and dashboard analytics.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum
from datetime import timedelta
import logging

from .models import (
    Customer,
    SyncJob,
    SentimentScore,
    SegmentSentiment,
    OverallSentiment,
    IndustryBaseline,
)
from .serializers import (
    CustomerSerializer,
    SyncJobSerializer,
    SentimentScoreSerializer,
    SegmentSentimentSerializer,
    OverallSentimentSerializer,
    IndustryBaselineSerializer,
    TimeRangeSerializer,
    DashboardSummarySerializer,
    SentimentTrendSerializer,
)

logger = logging.getLogger(__name__)


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Customer model.

    Provides read-only access to customer data with sentiment information.
    Supports filtering by industry, sentiment range, and search by company name.
    """

    queryset = Customer.objects.filter(is_active=True)
    serializer_class = CustomerSerializer
    permission_classes = [AllowAny]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["industry", "is_active"]
    search_fields = ["company_name", "contact_person", "industry"]
    ordering_fields = ["company_name", "industry", "created_at"]
    ordering = ["company_name"]

    def get_queryset(self):
        """Filter customers based on query parameters."""
        queryset = super().get_queryset()

        # Filter by sentiment range
        min_sentiment = self.request.query_params.get("min_sentiment")
        max_sentiment = self.request.query_params.get("max_sentiment")

        if min_sentiment or max_sentiment:
            # Get customers with recent sentiment scores
            recent_scores = SentimentScore.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            )

            if min_sentiment:
                recent_scores = recent_scores.filter(
                    sentiment_score__gte=float(min_sentiment)
                )
            if max_sentiment:
                recent_scores = recent_scores.filter(
                    sentiment_score__lte=float(max_sentiment)
                )

            customer_ids = recent_scores.values_list(
                "customer_id", flat=True
            ).distinct()
            queryset = queryset.filter(id__in=customer_ids)

        return queryset

    @action(detail=True, methods=["get"])
    def sentiment_history(self, request, pk=None):
        """Get sentiment history for a specific customer."""
        customer = self.get_object()

        # Parse time range
        time_serializer = TimeRangeSerializer(data=request.query_params)
        if not time_serializer.is_valid():
            return Response(time_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        time_data = time_serializer.validated_data
        start_date = time_data["start_date"]
        end_date = time_data["end_date"]

        # Get sentiment scores in time range
        scores = SentimentScore.objects.filter(
            customer=customer, created_at__gte=start_date, created_at__lte=end_date
        ).order_by("-created_at")

        serializer = SentimentScoreSerializer(scores, many=True)
        return Response(
            {
                "customer": CustomerSerializer(customer).data,
                "time_range": {
                    "start_date": start_date,
                    "end_date": end_date,
                },
                "sentiment_history": serializer.data,
                "count": scores.count(),
            }
        )

    @action(detail=True, methods=["get"])
    def reports_summary(self, request, pk=None):
        """Get FN/FP reports summary for a specific customer."""
        customer = self.get_object()

        # Parse time range
        time_serializer = TimeRangeSerializer(data=request.query_params)
        if not time_serializer.is_valid():
            return Response(time_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        time_data = time_serializer.validated_data
        start_date = time_data["start_date"]
        end_date = time_data["end_date"]

        # Get sync jobs in time range
        sync_jobs = SyncJob.objects.filter(
            customer=customer,
            status="completed",
            window_start__gte=start_date,
            window_start__lte=end_date,
        )

        # Calculate totals
        total_fn = sum(job.fn_count for job in sync_jobs)
        total_fp = sum(job.fp_count for job in sync_jobs)

        return Response(
            {
                "customer": CustomerSerializer(customer).data,
                "time_range": {
                    "start_date": start_date,
                    "end_date": end_date,
                },
                "summary": {
                    "total_fn_reports": total_fn,
                    "total_fp_reports": total_fp,
                    "total_reports": total_fn + total_fp,
                    "fn_fp_ratio": total_fn / total_fp if total_fp > 0 else 0,
                    "sync_jobs_count": sync_jobs.count(),
                },
                "recent_jobs": SyncJobSerializer(sync_jobs[:10], many=True).data,
            }
        )


class SentimentScoreViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for SentimentScore model.

    Provides access to calculated sentiment scores with filtering capabilities.
    """

    queryset = SentimentScore.objects.all()
    serializer_class = SentimentScoreSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["customer", "algorithm_used", "trend_direction"]
    ordering_fields = ["sentiment_score", "confidence_score", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter sentiment scores based on query parameters."""
        queryset = super().get_queryset()

        # Filter by time range
        time_serializer = TimeRangeSerializer(data=self.request.query_params)
        if time_serializer.is_valid():
            time_data = time_serializer.validated_data
            queryset = queryset.filter(
                created_at__gte=time_data["start_date"],
                created_at__lte=time_data["end_date"],
            )

        # Filter by sentiment range
        min_sentiment = self.request.query_params.get("min_sentiment")
        max_sentiment = self.request.query_params.get("max_sentiment")

        if min_sentiment:
            queryset = queryset.filter(sentiment_score__gte=float(min_sentiment))
        if max_sentiment:
            queryset = queryset.filter(sentiment_score__lte=float(max_sentiment))

        # Filter by industry
        industry = self.request.query_params.get("industry")
        if industry:
            queryset = queryset.filter(customer__industry=industry)

        return queryset

    @action(detail=False, methods=["get"])
    def trends(self, request):
        """Get sentiment trends over time."""
        # Parse time range
        time_serializer = TimeRangeSerializer(data=request.query_params)
        if not time_serializer.is_valid():
            return Response(time_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        time_data = time_serializer.validated_data
        start_date = time_data["start_date"]
        end_date = time_data["end_date"]

        # Get sentiment scores grouped by hour
        scores = (
            SentimentScore.objects.filter(
                created_at__gte=start_date, created_at__lte=end_date
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

        # Format response
        trend_data = []
        for score in scores:
            trend_data.append(
                {
                    "timestamp": score["hour"],
                    "sentiment_score": round(score["avg_sentiment"], 3),
                    "customer_count": score["customer_count"],
                    "total_reports": score["total_reports"] or 0,
                    "trend_direction": "stable",  # Could be calculated based on previous hour
                }
            )

        return Response(
            {
                "time_range": {
                    "start_date": start_date,
                    "end_date": end_date,
                },
                "trends": trend_data,
                "count": len(trend_data),
            }
        )


class SegmentSentimentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for SegmentSentiment model.

    Provides access to industry segment sentiment analysis.
    """

    queryset = SegmentSentiment.objects.all()
    serializer_class = SegmentSentimentSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["segment", "trend_direction"]
    ordering_fields = ["average_sentiment", "total_customers", "created_at"]
    ordering = ["-created_at", "segment"]

    def get_queryset(self):
        """Filter segment sentiment based on query parameters."""
        queryset = super().get_queryset()

        # Filter by time range
        time_serializer = TimeRangeSerializer(data=self.request.query_params)
        if time_serializer.is_valid():
            time_data = time_serializer.validated_data
            queryset = queryset.filter(
                created_at__gte=time_data["start_date"],
                created_at__lte=time_data["end_date"],
            )

        return queryset

    @action(detail=False, methods=["get"])
    def comparison(self, request):
        """Compare sentiment across all segments."""
        # Get latest segment data
        latest_segments = (
            SegmentSentiment.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=2)
            )
            .order_by("segment", "-created_at")
            .distinct("segment")
        )

        serializer = SegmentSentimentSerializer(latest_segments, many=True)

        # Calculate overall statistics
        if latest_segments:
            avg_sentiment = sum(s.average_sentiment for s in latest_segments) / len(
                latest_segments
            )
            best_segment = max(latest_segments, key=lambda s: s.average_sentiment)
            worst_segment = min(latest_segments, key=lambda s: s.average_sentiment)
        else:
            avg_sentiment = 0
            best_segment = None
            worst_segment = None

        return Response(
            {
                "segments": serializer.data,
                "summary": {
                    "overall_average": round(avg_sentiment, 3),
                    "total_segments": len(latest_segments),
                    "best_performing": {
                        "segment": best_segment.segment if best_segment else None,
                        "sentiment": (
                            best_segment.average_sentiment if best_segment else None
                        ),
                    },
                    "worst_performing": {
                        "segment": worst_segment.segment if worst_segment else None,
                        "sentiment": (
                            worst_segment.average_sentiment if worst_segment else None
                        ),
                    },
                },
            }
        )


class OverallSentimentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for OverallSentiment model.

    Provides access to product-wide sentiment metrics.
    """

    queryset = OverallSentiment.objects.all()
    serializer_class = OverallSentimentSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["overall_sentiment", "total_customers", "created_at"]
    ordering = ["-created_at"]

    @action(detail=False, methods=["get"])
    def latest(self, request):
        """Get the latest overall sentiment data."""
        latest = OverallSentiment.objects.order_by("-created_at").first()

        if not latest:
            return Response(
                {"message": "No overall sentiment data available"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OverallSentimentSerializer(latest)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        """Get dashboard summary data."""
        # Get latest overall sentiment
        latest_overall = OverallSentiment.objects.order_by("-created_at").first()

        if not latest_overall:
            return Response(
                {"message": "No sentiment data available"},
                status=status.HTTP_404_NOT_FOUND,
            )

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
                {
                    "segment": segment.segment,
                    "sentiment": segment.average_sentiment,
                    "customers": segment.total_customers,
                    "trend": segment.trend_direction,
                }
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
                {
                    "timestamp": score["hour"],
                    "sentiment_score": round(score["avg_sentiment"], 3),
                    "customer_count": score["customer_count"],
                    "total_reports": score["total_reports"] or 0,
                    "trend_direction": "stable",
                }
            )

        # Prepare dashboard data
        dashboard_data = {
            "overall_sentiment": latest_overall.overall_sentiment,
            "total_customers": latest_overall.total_customers,
            "total_reports_today": total_reports_today,
            "sentiment_trend": latest_overall.trend_direction,
            "top_performing_segment": latest_overall.top_performing_segment,
            "lowest_performing_segment": latest_overall.lowest_performing_segment,
            "recent_alerts": [],  # Could be populated with alerts logic
            "segment_breakdown": segment_breakdown,
            "hourly_sentiment": hourly_sentiment,
        }

        serializer = DashboardSummarySerializer(dashboard_data)
        return Response(serializer.data)


class IndustryBaselineViewSet(viewsets.ModelViewSet):
    """
    ViewSet for IndustryBaseline model.

    Provides CRUD operations for industry sentiment baselines.
    Admin-configurable reference values.
    """

    queryset = IndustryBaseline.objects.filter(is_active=True)
    serializer_class = IndustryBaselineSerializer
    permission_classes = [AllowAny]  # In production, this should be admin-only
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["industry", "is_active"]
    ordering_fields = ["industry", "baseline_sentiment", "created_at"]
    ordering = ["industry"]


class SyncJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for SyncJob model.

    Provides read-only access to sync job data for monitoring purposes.
    """

    queryset = SyncJob.objects.all()
    serializer_class = SyncJobSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["customer", "status"]
    ordering_fields = ["window_start", "created_at", "completed_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter sync jobs based on query parameters."""
        queryset = super().get_queryset()

        # Filter by time range
        time_serializer = TimeRangeSerializer(data=self.request.query_params)
        if time_serializer.is_valid():
            time_data = time_serializer.validated_data
            queryset = queryset.filter(
                window_start__gte=time_data["start_date"],
                window_start__lte=time_data["end_date"],
            )

        return queryset

    @action(detail=False, methods=["get"])
    def status_summary(self, request):
        """Get summary of sync job statuses."""
        # Get counts by status
        status_counts = (
            SyncJob.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )

        # Get recent job statistics
        recent_jobs = SyncJob.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        )

        total_reports = sum(
            job.fn_count + job.fp_count
            for job in recent_jobs
            if job.status == "completed"
        )

        return Response(
            {
                "status_breakdown": list(status_counts),
                "recent_24h": {
                    "total_jobs": recent_jobs.count(),
                    "completed_jobs": recent_jobs.filter(status="completed").count(),
                    "failed_jobs": recent_jobs.filter(status="failed").count(),
                    "total_reports_processed": total_reports,
                },
                "latest_jobs": SyncJobSerializer(
                    SyncJob.objects.order_by("-created_at")[:10], many=True
                ).data,
            }
        )
