"""
Database utilities for connecting to the source PostgreSQL database.

This module provides functions to connect to and query the external
PostgreSQL database containing customer and email sample data.
"""

import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from django.conf import settings
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SourceDatabaseConnection:
    """
    Manages connections to the source PostgreSQL database.
    """

    def __init__(self):
        self.connection = None
        self.db_config = settings.DATABASES["source_db"]

    def connect(self) -> bool:
        """
        Establish connection to the source database.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.connection = psycopg2.connect(
                host=self.db_config["HOST"],
                port=self.db_config["PORT"],
                database=self.db_config["NAME"],
                user=self.db_config["USER"],
                password=self.db_config["PASSWORD"],
                cursor_factory=RealDictCursor,
            )
            logger.info("Successfully connected to source database")
            return True
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to source database: {e}")
            return False

    def disconnect(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Disconnected from source database")

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """
        Execute a query and return results.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of dictionaries containing query results
        """
        if not self.connection:
            if not self.connect():
                return []

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except psycopg2.Error as e:
            logger.error(f"Query execution failed: {e}")
            return []


def get_customers_from_source() -> List[Dict[str, Any]]:
    """
    Fetch all customers from the source database.

    Returns:
        List of customer dictionaries
    """
    db = SourceDatabaseConnection()

    query = """
    SELECT 
        customer_id,
        company_name,
        industry,
        contact_person,
        phone,
        address,
        city,
        state,
        country,
        postal_code,
        created_at,
        updated_at
    FROM customers
    ORDER BY customer_id
    """

    try:
        customers = db.execute_query(query)
        logger.info(f"Fetched {len(customers)} customers from source database")
        return customers
    finally:
        db.disconnect()


def get_email_samples_for_time_window(
    start_time: datetime, end_time: datetime, customer_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Fetch email samples for a specific time window.

    Args:
        start_time: Start of time window
        end_time: End of time window
        customer_id: Optional customer ID filter

    Returns:
        List of email sample dictionaries
    """
    db = SourceDatabaseConnection()

    base_query = """
    SELECT 
        id,
        customer_id,
        sample_type,
        email_data,
        reported_at
    FROM email_samples
    WHERE reported_at >= %s AND reported_at < %s
    """

    params = [start_time, end_time]

    if customer_id:
        base_query += " AND customer_id = %s"
        params.append(customer_id)

    base_query += " ORDER BY reported_at"

    try:
        samples = db.execute_query(base_query, tuple(params))
        logger.info(
            f"Fetched {len(samples)} email samples for time window {start_time} to {end_time}"
        )
        return samples
    finally:
        db.disconnect()


def get_fn_fp_counts_for_window(
    start_time: datetime, end_time: datetime
) -> List[Dict[str, Any]]:
    """
    Get FN/FP counts per customer for a specific time window.

    Args:
        start_time: Start of time window
        end_time: End of time window

    Returns:
        List of dictionaries with customer_id, fn_count, fp_count
    """
    db = SourceDatabaseConnection()

    query = """
    SELECT 
        customer_id,
        COUNT(CASE WHEN sample_type = 'FN' THEN 1 END) as fn_count,
        COUNT(CASE WHEN sample_type = 'FP' THEN 1 END) as fp_count,
        COUNT(*) as total_count
    FROM email_samples
    WHERE reported_at >= %s AND reported_at < %s
    GROUP BY customer_id
    ORDER BY customer_id
    """

    try:
        counts = db.execute_query(query, (start_time, end_time))
        logger.info(
            f"Calculated FN/FP counts for {len(counts)} customers in window {start_time} to {end_time}"
        )
        return counts
    finally:
        db.disconnect()


def get_earliest_report_time() -> Optional[datetime]:
    """
    Get the earliest report time from email samples.

    Returns:
        Earliest report datetime or None if no data
    """
    db = SourceDatabaseConnection()

    query = "SELECT MIN(reported_at) as earliest_time FROM email_samples"

    try:
        result = db.execute_query(query)
        if result and result[0]["earliest_time"]:
            earliest = result[0]["earliest_time"]
            logger.info(f"Earliest report time: {earliest}")
            return earliest
        return None
    finally:
        db.disconnect()


def get_latest_report_time() -> Optional[datetime]:
    """
    Get the latest report time from email samples.

    Returns:
        Latest report datetime or None if no data
    """
    db = SourceDatabaseConnection()

    query = "SELECT MAX(reported_at) as latest_time FROM email_samples"

    try:
        result = db.execute_query(query)
        if result and result[0]["latest_time"]:
            latest = result[0]["latest_time"]
            logger.info(f"Latest report time: {latest}")
            return latest
        return None
    finally:
        db.disconnect()


def test_source_database_connection() -> bool:
    """
    Test the connection to the source database.

    Returns:
        bool: True if connection successful and tables exist
    """
    db = SourceDatabaseConnection()

    try:
        # Test connection
        if not db.connect():
            return False

        # Test if tables exist
        tables_query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('customers', 'email_samples')
        """

        tables = db.execute_query(tables_query)
        table_names = [table["table_name"] for table in tables]

        if "customers" not in table_names:
            logger.error("customers table not found in source database")
            return False

        if "email_samples" not in table_names:
            logger.error("email_samples table not found in source database")
            return False

        # Test data availability
        customer_count_query = "SELECT COUNT(*) as count FROM customers"
        customer_result = db.execute_query(customer_count_query)
        customer_count = customer_result[0]["count"] if customer_result else 0

        sample_count_query = "SELECT COUNT(*) as count FROM email_samples"
        sample_result = db.execute_query(sample_count_query)
        sample_count = sample_result[0]["count"] if sample_result else 0

        logger.info(
            f"Source database test successful: {customer_count} customers, {sample_count} email samples"
        )
        return True

    except Exception as e:
        logger.error(f"Source database test failed: {e}")
        return False
    finally:
        db.disconnect()
