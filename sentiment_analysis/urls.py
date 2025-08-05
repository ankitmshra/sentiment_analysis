"""
URL configuration for sentiment_analysis project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


def api_health(request):
    """Simple health check endpoint."""
    return JsonResponse(
        {
            "status": "healthy",
            "service": "Customer Sentiment Analysis API",
            "version": "1.0.0",
        }
    )


@require_http_methods(["GET"])
def api_root(request):
    """API root endpoint with available endpoints."""
    return JsonResponse(
        {
            "message": "Customer Sentiment Analysis API",
            "version": "1.0.0",
            "endpoints": {
                "admin": "/admin/",
                "api": "/api/",
                "graphql": "/graphql/",
                "docs": "/api/docs/",
                "redoc": "/api/redoc/",
                "health": "/health/",
                "django_rq": "/django-rq/",
            },
            "documentation": {
                "swagger": "/api/docs/",
                "redoc": "/api/redoc/",
                "graphql_playground": "/graphql/",
            },
        }
    )


urlpatterns = [
    # Admin interface
    path("admin/", admin.site.urls),
    # API root and health
    path("", api_root, name="api_root"),
    path("health/", api_health, name="api_health"),
    # API endpoints (will be created in Phase 3)
    path("api/", include("sentiment_api.urls")),
    # GraphQL endpoint (will be created in Phase 3)
    path("graphql/", include("sentiment_api.graphql_urls")),
    # Django RQ admin interface
    path("django-rq/", include("django_rq.urls")),
]

# Debug toolbar for development
if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
