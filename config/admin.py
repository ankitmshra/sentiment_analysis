"""
Django admin configuration for configuration models.

This module configures the Django admin interface for managing
database connections, sentiment configurations, and job settings.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from django.contrib import messages
from .models import DatabaseConfig, SentimentConfig, JobConfig


@admin.register(DatabaseConfig)
class DatabaseConfigAdmin(admin.ModelAdmin):
    """Admin configuration for DatabaseConfig model."""

    list_display = [
        "name",
        "host",
        "port",
        "database_name",
        "username",
        "is_active",
        "is_default",
        "test_status_colored",
        "last_tested",
    ]
    list_filter = [
        "is_active",
        "is_default",
        "test_status",
        "created_at",
        "last_tested",
    ]
    search_fields = [
        "name",
        "host",
        "database_name",
        "username",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "last_tested",
        "test_status",
        "test_error_message",
    ]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "is_active",
                    "is_default",
                )
            },
        ),
        (
            "Connection Details",
            {
                "fields": (
                    "host",
                    "port",
                    "database_name",
                    "username",
                    "password",
                )
            },
        ),
        (
            "Connection Settings",
            {
                "fields": (
                    "connection_timeout",
                    "max_connections",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Test Results",
            {
                "fields": (
                    "test_status",
                    "last_tested",
                    "test_error_message",
                ),
                "classes": ("collapse",),
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
    ordering = ["name"]
    list_per_page = 50
    actions = ["test_connections", "set_as_default"]

    def test_status_colored(self, obj):
        """Display test status with color coding."""
        colors = {
            "success": "green",
            "failed": "red",
            "pending": "orange",
            "not_tested": "gray",
        }
        color = colors.get(obj.test_status, "black")
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_test_status_display(),
        )

    test_status_colored.short_description = "Test Status"

    def test_connections(self, request, queryset):
        """Admin action to test database connections."""
        tested_count = 0
        success_count = 0

        for config in queryset:
            try:
                # Import here to avoid circular imports
                import psycopg2
                from psycopg2 import OperationalError

                # Test connection
                conn = psycopg2.connect(
                    host=config.host,
                    port=config.port,
                    database=config.database_name,
                    user=config.username,
                    password=config.password,
                    connect_timeout=config.connection_timeout,
                )
                conn.close()

                config.mark_test_success()
                success_count += 1
                tested_count += 1

            except OperationalError as e:
                config.mark_test_failed(str(e))
                tested_count += 1
            except Exception as e:
                config.mark_test_failed(f"Unexpected error: {str(e)}")
                tested_count += 1

        if success_count == tested_count:
            messages.success(
                request, f"All {tested_count} connections tested successfully."
            )
        else:
            messages.warning(
                request,
                f"{success_count}/{tested_count} connections successful. Check failed connections.",
            )

    test_connections.short_description = "Test selected database connections"

    def set_as_default(self, request, queryset):
        """Admin action to set a configuration as default."""
        if queryset.count() != 1:
            messages.error(
                request, "Please select exactly one configuration to set as default."
            )
            return

        config = queryset.first()
        config.is_default = True
        config.save()

        messages.success(
            request, f"'{config.name}' has been set as the default configuration."
        )

    set_as_default.short_description = "Set as default configuration"

    def save_model(self, request, obj, form, change):
        """Override save to handle default configuration logic."""
        try:
            super().save_model(request, obj, form, change)
            if obj.is_default:
                messages.success(
                    request, f"'{obj.name}' is now the default database configuration."
                )
        except ValidationError as e:
            messages.error(request, f"Error saving configuration: {e}")


@admin.register(SentimentConfig)
class SentimentConfigAdmin(admin.ModelAdmin):
    """Admin configuration for SentimentConfig model."""

    list_display = [
        "name",
        "default_algorithm",
        "default_window_hours",
        "time_decay_factor",
        "trend_weight",
        "enable_industry_normalization",
        "is_active",
        "is_default",
        "updated_at",
    ]
    list_filter = [
        "default_algorithm",
        "is_active",
        "is_default",
        "enable_industry_normalization",
        "created_at",
    ]
    search_fields = [
        "name",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "is_active",
                    "is_default",
                )
            },
        ),
        (
            "Algorithm Settings",
            {
                "fields": (
                    "default_algorithm",
                    "default_window_hours",
                )
            },
        ),
        (
            "Weighted Average Parameters",
            {
                "fields": ("time_decay_factor",),
                "description": "Parameters for weighted average algorithm",
            },
        ),
        (
            "Trend Analysis Parameters",
            {
                "fields": ("trend_weight",),
                "description": "Parameters for trend-adjusted algorithm",
            },
        ),
        (
            "Confidence & Normalization",
            {
                "fields": (
                    "min_reports_for_confidence",
                    "enable_industry_normalization",
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
    ordering = ["name"]
    list_per_page = 50
    actions = ["set_as_default", "duplicate_config"]

    def set_as_default(self, request, queryset):
        """Admin action to set a configuration as default."""
        if queryset.count() != 1:
            messages.error(
                request, "Please select exactly one configuration to set as default."
            )
            return

        config = queryset.first()
        config.is_default = True
        config.save()

        messages.success(
            request,
            f"'{config.name}' has been set as the default sentiment configuration.",
        )

    set_as_default.short_description = "Set as default configuration"

    def duplicate_config(self, request, queryset):
        """Admin action to duplicate configurations."""
        duplicated_count = 0

        for config in queryset:
            # Create a copy
            config.pk = None
            config.name = f"{config.name} (Copy)"
            config.is_default = False
            config.save()
            duplicated_count += 1

        messages.success(request, f"Duplicated {duplicated_count} configuration(s).")

    duplicate_config.short_description = "Duplicate selected configurations"

    def save_model(self, request, obj, form, change):
        """Override save to handle default configuration logic."""
        try:
            super().save_model(request, obj, form, change)
            if obj.is_default:
                messages.success(
                    request, f"'{obj.name}' is now the default sentiment configuration."
                )
        except ValidationError as e:
            messages.error(request, f"Error saving configuration: {e}")


@admin.register(JobConfig)
class JobConfigAdmin(admin.ModelAdmin):
    """Admin configuration for JobConfig model."""

    list_display = [
        "name",
        "sync_interval_minutes",
        "sync_batch_size",
        "sentiment_delay_minutes",
        "segment_delay_minutes",
        "overall_delay_minutes",
        "max_retries",
        "is_active",
        "is_default",
        "updated_at",
    ]
    list_filter = [
        "is_active",
        "is_default",
        "created_at",
    ]
    search_fields = [
        "name",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "is_active",
                    "is_default",
                )
            },
        ),
        (
            "Sync Job Settings",
            {
                "fields": (
                    "sync_interval_minutes",
                    "sync_batch_size",
                ),
                "description": "Settings for data synchronization jobs",
            },
        ),
        (
            "Processing Delays",
            {
                "fields": (
                    "sentiment_delay_minutes",
                    "segment_delay_minutes",
                    "overall_delay_minutes",
                ),
                "description": "Delays between different processing stages",
            },
        ),
        (
            "Retry & Cleanup Settings",
            {
                "fields": (
                    "max_retries",
                    "retry_delay_minutes",
                    "cleanup_old_jobs_days",
                ),
                "classes": ("collapse",),
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
    ordering = ["name"]
    list_per_page = 50
    actions = ["set_as_default", "duplicate_config"]

    def set_as_default(self, request, queryset):
        """Admin action to set a configuration as default."""
        if queryset.count() != 1:
            messages.error(
                request, "Please select exactly one configuration to set as default."
            )
            return

        config = queryset.first()
        config.is_default = True
        config.save()

        messages.success(
            request, f"'{config.name}' has been set as the default job configuration."
        )

    set_as_default.short_description = "Set as default configuration"

    def duplicate_config(self, request, queryset):
        """Admin action to duplicate configurations."""
        duplicated_count = 0

        for config in queryset:
            # Create a copy
            config.pk = None
            config.name = f"{config.name} (Copy)"
            config.is_default = False
            config.save()
            duplicated_count += 1

        messages.success(request, f"Duplicated {duplicated_count} configuration(s).")

    duplicate_config.short_description = "Duplicate selected configurations"

    def save_model(self, request, obj, form, change):
        """Override save to handle default configuration logic."""
        try:
            super().save_model(request, obj, form, change)
            if obj.is_default:
                messages.success(
                    request, f"'{obj.name}' is now the default job configuration."
                )
        except ValidationError as e:
            messages.error(request, f"Error saving configuration: {e}")

    def get_form(self, request, obj=None, **kwargs):
        """Customize form to add help text and validation."""
        form = super().get_form(request, obj, **kwargs)

        # Add custom help text
        if "sync_interval_minutes" in form.base_fields:
            form.base_fields["sync_interval_minutes"].help_text = (
                "How often to run sync jobs. Recommended: 60 minutes for production, "
                "15-30 minutes for development."
            )

        if "sync_batch_size" in form.base_fields:
            form.base_fields["sync_batch_size"].help_text = (
                "Number of records to process in each batch. Larger batches are more "
                "efficient but use more memory. Recommended: 1000-5000."
            )

        return form


# Custom admin site configuration
admin.site.site_header = "Sentiment Analysis Administration"
admin.site.site_title = "Sentiment Analysis Admin"
admin.site.index_title = "Welcome to Sentiment Analysis Administration"
