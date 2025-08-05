"""
URL configuration for sentiment_api app.

This module contains REST API endpoints for sentiment analysis.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from .views import (
    CustomerViewSet,
    SentimentScoreViewSet,
    SegmentSentimentViewSet,
    OverallSentimentViewSet,
    IndustryBaselineViewSet,
    SyncJobViewSet,
)

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"sentiment-scores", SentimentScoreViewSet, basename="sentimentscore")
router.register(
    r"segment-sentiment", SegmentSentimentViewSet, basename="segmentsentiment"
)
router.register(
    r"overall-sentiment", OverallSentimentViewSet, basename="overallsentiment"
)
router.register(
    r"industry-baselines", IndustryBaselineViewSet, basename="industrybaseline"
)
router.register(r"sync-jobs", SyncJobViewSet, basename="syncjob")

app_name = "sentiment_api"

urlpatterns = [
    # API endpoints
    path("", include(router.urls)),
    # API Documentation
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="sentiment_api:schema"),
        name="swagger-ui",
    ),
    path(
        "redoc/",
        SpectacularRedocView.as_view(url_name="sentiment_api:schema"),
        name="redoc",
    ),
]
