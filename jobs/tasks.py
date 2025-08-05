"""
Background task implementations for sentiment analysis system.

This module contains the actual task implementations that are executed
by the scheduler for data sync, sentiment calculation, and analysis.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from config.models import DatabaseConfig, SentimentConfig
from sentiment_api.models import (
    Customer,
    SyncJob,
    SentimentScore,
    SegmentSentiment,
    OverallSentiment,
    IndustryBaseline,
)

logger = logging.getLogger(__name__)


def sync_data_from_source():
    """
    Sync FN/FP data from the external PostgreSQL database.

    This job runs hourly to extract FN/FP counts for each customer
    in 1-hour windows and store them in the local database.
    """
    logger.info("Starting data sync job")

    try:
        from .database_utils import (
            get_fn_fp_counts_for_window,
            get_customers_from_source,
            test_source_database_connection,
            get_earliest_report_time,
        )

        # Test database connection first
        if not test_source_database_connection():
            logger.error("Cannot connect to source database. Aborting sync job.")
            return

        # Sync customers first
        sync_customers_from_source()

        # Get the current hour window
        now = timezone.now()
        window_start = now.replace(minute=0, second=0, microsecond=0)
        window_end = window_start + timedelta(hours=1)

        # For first run, check if we need to backfill historical data
        if not SyncJob.objects.exists():
            logger.info("First run detected. Starting historical data backfill.")
            backfill_historical_data()
            return

        # Check if we already have data for this window
        existing_jobs = SyncJob.objects.filter(
            window_start=window_start, status="completed"
        )

        if existing_jobs.exists():
            logger.info(f"Data already synced for window {window_start}")
            return

        # Get FN/FP counts for the current window
        fn_fp_counts = get_fn_fp_counts_for_window(window_start, window_end)

        if not fn_fp_counts:
            logger.info(f"No data found for window {window_start} to {window_end}")
            # Create empty sync jobs for all customers to maintain consistency
            customers = Customer.objects.all()
            for customer in customers:
                SyncJob.objects.create(
                    customer=customer,
                    window_start=window_start,
                    window_end=window_end,
                    fn_count=0,
                    fp_count=0,
                    status="completed",
                    started_at=now,
                    completed_at=timezone.now(),
                )
            return

        # Create sync jobs for each customer with real data
        jobs_created = 0
        for count_data in fn_fp_counts:
            try:
                customer = Customer.objects.get(customer_id=count_data["customer_id"])

                sync_job = SyncJob.objects.create(
                    customer=customer,
                    window_start=window_start,
                    window_end=window_end,
                    fn_count=count_data["fn_count"] or 0,
                    fp_count=count_data["fp_count"] or 0,
                    status="completed",
                    started_at=now,
                    completed_at=timezone.now(),
                )

                jobs_created += 1
                logger.info(
                    f"Created sync job for customer {customer.company_name}: "
                    f"FN={count_data['fn_count']}, FP={count_data['fp_count']}"
                )

            except Customer.DoesNotExist:
                logger.warning(
                    f"Customer with ID {count_data['customer_id']} not found in local database"
                )
                continue

        logger.info(
            f"Data sync completed for window {window_start}. Created {jobs_created} sync jobs."
        )

    except Exception as e:
        logger.error(f"Data sync job failed: {e}")
        raise


def sync_customers_from_source():
    """
    Sync customer data from the external PostgreSQL database.
    """
    logger.info("Starting customer sync")

    try:
        from .database_utils import get_customers_from_source

        source_customers = get_customers_from_source()

        customers_created = 0
        customers_updated = 0

        for customer_data in source_customers:
            customer, created = Customer.objects.update_or_create(
                customer_id=customer_data["customer_id"],
                defaults={
                    "company_name": customer_data["company_name"],
                    "industry": customer_data["industry"],
                    "contact_person": customer_data["contact_person"],
                    "phone": customer_data.get("phone", ""),
                    "address": customer_data.get("address", ""),
                    "city": customer_data.get("city", ""),
                    "state": customer_data.get("state", ""),
                    "country": customer_data.get("country", ""),
                    "postal_code": customer_data.get("postal_code", ""),
                    "is_active": True,
                    "created_at": customer_data.get("created_at", timezone.now()),
                    "updated_at": customer_data.get("updated_at", timezone.now()),
                },
            )

            if created:
                customers_created += 1
            else:
                customers_updated += 1

        logger.info(
            f"Customer sync completed: {customers_created} created, {customers_updated} updated"
        )

    except Exception as e:
        logger.error(f"Customer sync failed: {e}")
        raise


def backfill_historical_data():
    """
    Backfill historical data from the earliest report time to now in 1-hour windows.
    """
    logger.info("Starting historical data backfill")

    try:
        from .database_utils import (
            get_earliest_report_time,
            get_fn_fp_counts_for_window,
        )

        earliest_time = get_earliest_report_time()
        if not earliest_time:
            logger.warning("No historical data found in source database")
            return

        # Start from the earliest hour - make sure both times are timezone-aware
        if earliest_time.tzinfo is None:
            # If earliest_time is naive, make it timezone-aware
            from django.utils import timezone as django_timezone

            earliest_time = django_timezone.make_aware(earliest_time)

        current_window = earliest_time.replace(minute=0, second=0, microsecond=0)
        now = timezone.now().replace(minute=0, second=0, microsecond=0)

        jobs_created = 0
        windows_processed = 0

        while current_window < now:
            window_end = current_window + timedelta(hours=1)

            # Get FN/FP counts for this window
            fn_fp_counts = get_fn_fp_counts_for_window(current_window, window_end)

            # Create sync jobs for this window
            for count_data in fn_fp_counts:
                try:
                    customer = Customer.objects.get(
                        customer_id=count_data["customer_id"]
                    )

                    sync_job = SyncJob.objects.create(
                        customer=customer,
                        window_start=current_window,
                        window_end=window_end,
                        fn_count=count_data["fn_count"] or 0,
                        fp_count=count_data["fp_count"] or 0,
                        status="completed",
                        started_at=current_window,
                        completed_at=current_window + timedelta(minutes=1),
                    )

                    jobs_created += 1

                except Customer.DoesNotExist:
                    logger.warning(
                        f"Customer with ID {count_data['customer_id']} not found"
                    )
                    continue

            windows_processed += 1
            current_window = window_end

            # Log progress every 24 hours
            if windows_processed % 24 == 0:
                logger.info(
                    f"Backfill progress: {windows_processed} windows processed, {jobs_created} jobs created"
                )

        logger.info(
            f"Historical data backfill completed: {windows_processed} windows, {jobs_created} sync jobs created"
        )

    except Exception as e:
        logger.error(f"Historical data backfill failed: {e}")
        raise


def calculate_sentiment_scores():
    """
    Calculate sentiment scores for completed sync jobs.

    This job processes sync jobs that don't have sentiment scores yet
    and calculates sentiment using the configured algorithm.
    """
    logger.info("Starting sentiment calculation job")

    try:
        # Get sentiment configuration
        sentiment_config = SentimentConfig.objects.filter(
            is_active=True, is_default=True
        ).first()

        if not sentiment_config:
            logger.warning("No active sentiment configuration found. Using defaults.")
            # Create default config
            sentiment_config = SentimentConfig.objects.create(
                name="Default Configuration",
                default_algorithm="weighted_average",
                default_window_hours=24,
                time_decay_factor=0.9,
                min_reports_for_confidence=5,
                is_active=True,
                is_default=True,
            )

        # Find completed sync jobs without sentiment scores
        completed_jobs = SyncJob.objects.filter(status="completed").select_related(
            "customer"
        )

        # Filter out jobs that already have sentiment scores
        jobs_without_scores = []
        for job in completed_jobs:
            if not SentimentScore.objects.filter(job_id=job.job_id).exists():
                jobs_without_scores.append(job)

        scores_created = 0

        for sync_job in jobs_without_scores:
            try:
                with transaction.atomic():
                    sentiment_score = calculate_sentiment_for_job(
                        sync_job, sentiment_config
                    )
                    scores_created += 1

            except Exception as e:
                logger.error(
                    f"Failed to calculate sentiment for job {sync_job.job_id}: {e}"
                )
                continue

        logger.info(f"Sentiment calculation completed: {scores_created} scores created")

    except Exception as e:
        logger.error(f"Sentiment calculation job failed: {e}")
        raise


def calculate_sentiment_for_job(
    sync_job: SyncJob, config: SentimentConfig
) -> SentimentScore:
    """Calculate sentiment score for a specific sync job."""
    fn_count = sync_job.fn_count
    fp_count = sync_job.fp_count
    total_reports = fn_count + fp_count

    if total_reports == 0:
        sentiment_score = 0.5  # Neutral when no reports
        confidence = 0.0
    else:
        # Calculate sentiment based on algorithm
        if config.default_algorithm == "simple_ratio":
            sentiment_score = fp_count / total_reports
        elif config.default_algorithm == "weighted_average":
            sentiment_score = calculate_weighted_average_sentiment(sync_job, config)
        else:
            # Default to simple ratio
            sentiment_score = fp_count / total_reports

        # Calculate confidence based on report count
        confidence = min(total_reports / config.min_reports_for_confidence, 1.0)

    # Determine trend direction
    trend_direction = determine_customer_trend(sync_job.customer)

    # Create sentiment score record
    return SentimentScore.objects.create(
        job_id=sync_job.job_id,
        customer=sync_job.customer,
        sentiment_score=sentiment_score,
        algorithm_used=config.default_algorithm,
        calculation_window_hours=config.default_window_hours,
        fn_count_used=fn_count,
        fp_count_used=fp_count,
        confidence_score=confidence,
        trend_direction=trend_direction,
    )


def calculate_weighted_average_sentiment(
    sync_job: SyncJob, config: SentimentConfig
) -> float:
    """Calculate weighted average sentiment score."""
    # Get recent sync jobs for this customer
    recent_jobs = SyncJob.objects.filter(
        customer=sync_job.customer,
        status="completed",
        window_start__gte=sync_job.window_start
        - timedelta(hours=config.default_window_hours),
    ).order_by("-window_start")

    if not recent_jobs:
        return 0.5

    weighted_sum = 0.0
    weight_sum = 0.0

    for i, job in enumerate(recent_jobs):
        total = job.fn_count + job.fp_count
        if total > 0:
            score = job.fp_count / total
            weight = config.time_decay_factor**i
            weighted_sum += score * weight
            weight_sum += weight

    return weighted_sum / weight_sum if weight_sum > 0 else 0.5


def determine_customer_trend(customer: Customer) -> str:
    """Determine sentiment trend for customer."""
    # Get last few sentiment scores
    recent_scores = SentimentScore.objects.filter(customer=customer).order_by(
        "-created_at"
    )[:3]

    if len(recent_scores) < 2:
        return "stable"

    scores = [score.sentiment_score for score in recent_scores]

    # Simple trend calculation
    if scores[0] > scores[1] * 1.05:  # 5% improvement
        return "improving"
    elif scores[0] < scores[1] * 0.95:  # 5% decline
        return "declining"
    else:
        return "stable"


def calculate_segment_sentiment():
    """
    Calculate segment-wise sentiment analysis.

    This job groups customers by industry and calculates
    aggregate sentiment metrics for each segment.
    """
    logger.info("Starting segment sentiment calculation")

    try:
        # Get unique industries
        industries = Customer.objects.values_list("industry", flat=True).distinct()

        segments_processed = 0
        current_time = timezone.now()

        for industry in industries:
            try:
                with transaction.atomic():
                    calculate_sentiment_for_segment(industry, current_time)
                    segments_processed += 1

            except Exception as e:
                logger.error(
                    f"Failed to calculate segment sentiment for {industry}: {e}"
                )
                continue

        logger.info(
            f"Segment sentiment calculation completed: {segments_processed} segments processed"
        )

    except Exception as e:
        logger.error(f"Segment sentiment calculation failed: {e}")
        raise


def calculate_sentiment_for_segment(industry: str, calculation_time: datetime):
    """Calculate sentiment for a specific industry segment."""
    # Get recent sentiment scores for this industry
    recent_scores = SentimentScore.objects.filter(
        customer__industry=industry,
        created_at__gte=calculation_time - timedelta(hours=24),
    ).select_related("customer")

    if not recent_scores:
        return

    # Calculate aggregate metrics
    scores = [score.sentiment_score for score in recent_scores]
    fn_counts = [score.fn_count_used for score in recent_scores]
    fp_counts = [score.fp_count_used for score in recent_scores]

    average_sentiment = sum(scores) / len(scores)
    median_sentiment = sorted(scores)[len(scores) // 2]

    # Calculate standard deviation
    variance = sum((x - average_sentiment) ** 2 for x in scores) / len(scores)
    std_dev = variance**0.5

    # Determine trend
    trend_direction = determine_segment_trend(industry)

    # Create segment sentiment record
    SegmentSentiment.objects.create(
        segment=industry,
        total_customers=len(set(score.customer.id for score in recent_scores)),
        average_sentiment=average_sentiment,
        median_sentiment=median_sentiment,
        sentiment_std_dev=std_dev,
        total_fn_count=sum(fn_counts),
        total_fp_count=sum(fp_counts),
        trend_direction=trend_direction,
        calculation_window_hours=24,
    )


def determine_segment_trend(industry: str) -> str:
    """Determine trend for industry segment."""
    # Get last two segment records
    recent_segments = SegmentSentiment.objects.filter(segment=industry).order_by(
        "-created_at"
    )[:2]

    if len(recent_segments) < 2:
        return "stable"

    current_score = recent_segments[0].average_sentiment
    previous_score = recent_segments[1].average_sentiment

    if current_score > previous_score * 1.05:  # 5% improvement threshold
        return "improving"
    elif current_score < previous_score * 0.95:  # 5% decline threshold
        return "declining"
    else:
        return "stable"


def calculate_overall_sentiment():
    """
    Calculate overall product sentiment.

    This job aggregates all customer sentiment data and calculates
    product-wide metrics and performance indicators.
    """
    logger.info("Starting overall sentiment calculation")

    try:
        current_time = timezone.now()

        # Get recent sentiment scores
        recent_scores = SentimentScore.objects.filter(
            created_at__gte=current_time - timedelta(hours=24)
        ).select_related("customer")

        if not recent_scores:
            logger.warning("No recent sentiment scores found")
            return

        # Calculate overall metrics
        scores = [score.sentiment_score for score in recent_scores]
        fn_counts = [score.fn_count_used for score in recent_scores]
        fp_counts = [score.fp_count_used for score in recent_scores]

        overall_sentiment = sum(scores) / len(scores)

        # Calculate weighted sentiment (by report volume)
        total_reports = [fn + fp for fn, fp in zip(fn_counts, fp_counts)]
        if sum(total_reports) > 0:
            weighted_sentiment = sum(
                score * reports for score, reports in zip(scores, total_reports)
            ) / sum(total_reports)
        else:
            weighted_sentiment = overall_sentiment

        # Calculate variance
        variance = sum((x - overall_sentiment) ** 2 for x in scores) / len(scores)

        # Get segment performance
        segment_performance = get_segment_performance(current_time)

        # Determine trend
        trend_direction = determine_overall_trend()

        # Create overall sentiment record
        OverallSentiment.objects.create(
            total_customers=len(set(score.customer.id for score in recent_scores)),
            overall_sentiment=overall_sentiment,
            weighted_sentiment=weighted_sentiment,
            sentiment_variance=variance,
            total_fn_count=sum(fn_counts),
            total_fp_count=sum(fp_counts),
            trend_direction=trend_direction,
            top_performing_segment=segment_performance["top"],
            lowest_performing_segment=segment_performance["bottom"],
            calculation_window_hours=24,
        )

        logger.info(f"Overall sentiment calculation completed: {overall_sentiment:.3f}")

    except Exception as e:
        logger.error(f"Overall sentiment calculation failed: {e}")
        raise


def get_segment_performance(calculation_time: datetime) -> Dict[str, str]:
    """Get top and bottom performing segments."""
    recent_segments = SegmentSentiment.objects.filter(
        created_at__gte=calculation_time - timedelta(hours=1)
    ).order_by("-average_sentiment")

    if recent_segments:
        top_segment = recent_segments.first().segment
        bottom_segment = recent_segments.last().segment
    else:
        top_segment = "Unknown"
        bottom_segment = "Unknown"

    return {"top": top_segment, "bottom": bottom_segment}


def determine_overall_trend() -> str:
    """Determine overall sentiment trend."""
    # Get last two overall records
    recent_overall = OverallSentiment.objects.order_by("-created_at")[:2]

    if len(recent_overall) < 2:
        return "stable"

    current_score = recent_overall[0].overall_sentiment
    previous_score = recent_overall[1].overall_sentiment

    if current_score > previous_score * 1.03:  # 3% improvement threshold
        return "improving"
    elif current_score < previous_score * 0.97:  # 3% decline threshold
        return "declining"
    else:
        return "stable"
