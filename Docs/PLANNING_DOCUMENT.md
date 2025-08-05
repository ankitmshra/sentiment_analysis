# Customer Sentiment Analysis API - Complete Planning Document

## Executive Summary

This document outlines the complete plan for developing a Django-based API service that analyzes customer sentiment using False Negative (FN) and False Positive (FP) email reporting data. The system will provide proactive sentiment analysis through statistical modeling, hourly background processing, and dual API interfaces (REST + GraphQL).

## System Architecture Overview

### High-Level Architecture
```
External PostgreSQL (Source Data) 
    ↓ (Hourly Sync Jobs)
Local SQLite Database (Processing & Storage)
    ↓ (API Layer)
REST Endpoints + GraphQL Playground
    ↓ (Frontend Integration)
Interactive Dashboard with Real-time Queries
```

### Core Components
1. **Data Sync Layer**: Hourly background jobs to extract FN/FP data
2. **Sentiment Engine**: Statistical modeling for sentiment calculation
3. **API Layer**: Dual REST/GraphQL interfaces
4. **Admin Interface**: Configuration management via Django admin
5. **Dashboard Support**: Real-time GraphQL queries for visualization

## Database Schema Design

### External PostgreSQL Schema (Read-Only)
```sql
-- Source database: localhost:9876/email_security (admin/securepass123)
customers (
    customer_id SERIAL PRIMARY KEY,
    company_name VARCHAR(255),
    industry VARCHAR(100),
    contact_person VARCHAR(255),
    phone VARCHAR(20),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

email_samples (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    sample_type VARCHAR(2) CHECK (sample_type IN ('FN', 'FP')),
    email_data JSONB,
    reported_at TIMESTAMP
);
```

### Local SQLite Schema (Processing)
```python
# Django Models for Local Database

class Customer(models.Model):
    """Local copy of customer data for processing"""
    customer_id = models.IntegerField(unique=True)
    company_name = models.CharField(max_length=255)
    industry = models.CharField(max_length=100)
    contact_person = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    synced_at = models.DateTimeField(auto_now=True)

class SyncJob(models.Model):
    """Hourly FN/FP count aggregations"""
    job_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    fn_count = models.IntegerField(default=0)
    fp_count = models.IntegerField(default=0)
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    completed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['customer', 'window_start']

class SentimentScore(models.Model):
    """Customer sentiment calculations (immutable)"""
    job_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    sentiment_score = models.FloatField()
    calculation_method = models.CharField(max_length=50)
    fn_count = models.IntegerField()
    fp_count = models.IntegerField()
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

class SegmentSentiment(models.Model):
    """Industry-wise sentiment aggregations"""
    job_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    industry = models.CharField(max_length=100)
    total_customers = models.IntegerField()
    avg_sentiment_score = models.FloatField()
    total_fn_count = models.IntegerField()
    total_fp_count = models.IntegerField()
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    completed_at = models.DateTimeField(auto_now_add=True)

class OverallSentiment(models.Model):
    """Product-wide sentiment metrics"""
    job_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    total_customers = models.IntegerField()
    avg_sentiment_score = models.FloatField()
    total_fn_count = models.IntegerField()
    total_fp_count = models.IntegerField()
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    completed_at = models.DateTimeField(auto_now_add=True)

class IndustryBaseline(models.Model):
    """Configurable industry sentiment baselines"""
    industry = models.CharField(max_length=100, unique=True)
    baseline_score = models.FloatField(default=0.5)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class DatabaseConfig(models.Model):
    """Admin-configurable database connection settings"""
    name = models.CharField(max_length=100, default='source_db')
    host = models.CharField(max_length=255, default='localhost')
    port = models.IntegerField(default=9876)
    database = models.CharField(max_length=100, default='email_security')
    username = models.CharField(max_length=100, default='admin')
    password = models.CharField(max_length=255, default='securepass123')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

## Sentiment Calculation Algorithms

### 1. Simple Ratio Method (Baseline)
```python
def simple_ratio(fn_count, fp_count):
    """Basic FP/(FN+FP) ratio - higher FP indicates worse sentiment"""
    total = fn_count + fp_count
    if total == 0:
        return 0.5  # Neutral when no data
    
    # Invert ratio so higher score = better sentiment
    fp_ratio = fp_count / total
    return 1.0 - fp_ratio  # Convert to sentiment score (0-1)
```

### 2. Weighted Average Method (Recommended)
```python
def weighted_average_sentiment(historical_data, decay_factor=0.9):
    """Time-decay weighted average with recent data emphasis"""
    if not historical_data:
        return 0.5
    
    weighted_sum = 0
    weight_total = 0
    
    # Sort by time (most recent first)
    sorted_data = sorted(historical_data, key=lambda x: x['timestamp'], reverse=True)
    
    for i, data in enumerate(sorted_data):
        weight = decay_factor ** i
        fn, fp = data['fn_count'], data['fp_count']
        
        # Calculate sentiment for this period
        total = fn + fp
        if total > 0:
            sentiment = 1.0 - (fp / total)  # Higher FP = lower sentiment
        else:
            sentiment = 0.5
        
        weighted_sum += sentiment * weight
        weight_total += weight
    
    return weighted_sum / weight_total if weight_total > 0 else 0.5
```

### 3. Trend-Adjusted Method (Advanced)
```python
def trend_adjusted_sentiment(current_score, historical_scores, trend_weight=0.2):
    """Adjust sentiment based on trend velocity"""
    if len(historical_scores) < 2:
        return current_score
    
    # Calculate trend (velocity of change)
    recent_trend = current_score - historical_scores[-1]
    
    # Apply trend adjustment
    adjusted_score = current_score + (recent_trend * trend_weight)
    
    # Clamp to valid range [0, 1]
    return max(0.0, min(1.0, adjusted_score))
```

### 4. Industry-Normalized Method
```python
def industry_normalized_sentiment(raw_score, industry_baseline):
    """Normalize sentiment relative to industry baseline"""
    if industry_baseline == 0:
        return raw_score
    
    # Calculate relative performance
    relative_score = raw_score / industry_baseline
    
    # Normalize to 0-1 scale (0.5 = at baseline)
    normalized = 0.5 + ((relative_score - 1.0) * 0.5)
    
    return max(0.0, min(1.0, normalized))
```

## Background Job Processing Pipeline

### Job Sequence (Every Hour)
```
00:00 - Data Sync Job (Extract FN/FP counts)
00:05 - Sentiment Calculation Job
00:10 - Segment Analysis Job
00:15 - Overall Metrics Job
```

### 1. Data Sync Job Implementation
```python
@job('default', timeout=300)
def sync_customer_data():
    """Extract FN/FP counts from external DB for last hour"""
    
    # Get active database configuration
    db_config = DatabaseConfig.objects.filter(is_active=True).first()
    if not db_config:
        logger.error("No active database configuration found")
        return
    
    # Calculate time window
    end_time = timezone.now().replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(hours=1)
    
    # Connect to external database
    external_db = get_external_db_connection(db_config)
    
    try:
        # Query FN/FP counts per customer for the hour
        query = """
        SELECT 
            customer_id,
            sample_type,
            COUNT(*) as count
        FROM email_samples 
        WHERE reported_at >= %s AND reported_at < %s
        GROUP BY customer_id, sample_type
        """
        
        with external_db.cursor() as cursor:
            cursor.execute(query, [start_time, end_time])
            results = cursor.fetchall()
        
        # Process results and create sync jobs
        customer_data = {}
        for customer_id, sample_type, count in results:
            if customer_id not in customer_data:
                customer_data[customer_id] = {'fn_count': 0, 'fp_count': 0}
            
            if sample_type == 'FN':
                customer_data[customer_id]['fn_count'] = count
            elif sample_type == 'FP':
                customer_data[customer_id]['fp_count'] = count
        
        # Create sync job records
        for customer_id, counts in customer_data.items():
            customer = Customer.objects.get(customer_id=customer_id)
            
            SyncJob.objects.update_or_create(
                customer=customer,
                window_start=start_time,
                defaults={
                    'window_end': end_time,
                    'fn_count': counts['fn_count'],
                    'fp_count': counts['fp_count']
                }
            )
        
        logger.info(f"Synced data for {len(customer_data)} customers")
        
    except Exception as e:
        logger.error(f"Data sync failed: {str(e)}")
        raise
    finally:
        external_db.close()
```

### 2. Sentiment Calculation Job
```python
@job('default', timeout=300)
def calculate_sentiment_scores():
    """Calculate sentiment scores for latest sync jobs"""
    
    # Get latest sync jobs that don't have sentiment scores
    latest_sync_jobs = SyncJob.objects.filter(
        sentimentscore__isnull=True
    ).select_related('customer')
    
    for sync_job in latest_sync_jobs:
        try:
            # Get historical data for weighted calculation
            historical_data = SyncJob.objects.filter(
                customer=sync_job.customer,
                window_start__lt=sync_job.window_start
            ).order_by('-window_start')[:10]  # Last 10 hours
            
            # Calculate sentiment using weighted average method
            historical_scores = []
            for hist_job in historical_data:
                score = simple_ratio(hist_job.fn_count, hist_job.fp_count)
                historical_scores.append({
                    'timestamp': hist_job.window_start,
                    'fn_count': hist_job.fn_count,
                    'fp_count': hist_job.fp_count,
                    'score': score
                })
            
            # Calculate current sentiment
            if historical_scores:
                sentiment_score = weighted_average_sentiment(historical_scores)
            else:
                sentiment_score = simple_ratio(sync_job.fn_count, sync_job.fp_count)
            
            # Apply industry normalization if baseline exists
            try:
                baseline = IndustryBaseline.objects.get(
                    industry=sync_job.customer.industry
                )
                sentiment_score = industry_normalized_sentiment(
                    sentiment_score, baseline.baseline_score
                )
            except IndustryBaseline.DoesNotExist:
                pass  # Use raw score if no baseline
            
            # Create sentiment score record
            SentimentScore.objects.create(
                customer=sync_job.customer,
                sentiment_score=sentiment_score,
                calculation_method='weighted_average_normalized',
                fn_count=sync_job.fn_count,
                fp_count=sync_job.fp_count,
                window_start=sync_job.window_start,
                window_end=sync_job.window_end
            )
            
        except Exception as e:
            logger.error(f"Sentiment calculation failed for customer {sync_job.customer.customer_id}: {str(e)}")
    
    logger.info(f"Calculated sentiment for {latest_sync_jobs.count()} customers")
```

## API Design

### REST API Endpoints

#### Customer Endpoints
```python
# /api/customers/
class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['industry', 'city', 'state', 'country']
    ordering_fields = ['company_name', 'created_at']
    
    @action(detail=True, methods=['get'])
    def sentiment_history(self, request, pk=None):
        """Get sentiment history for a customer"""
        customer = self.get_object()
        
        # Parse time range parameters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = SentimentScore.objects.filter(customer=customer)
        
        if start_date:
            queryset = queryset.filter(window_start__gte=start_date)
        if end_date:
            queryset = queryset.filter(window_end__lte=end_date)
        
        serializer = SentimentScoreSerializer(queryset, many=True)
        return Response(serializer.data)
```

#### Sentiment Analysis Endpoints
```python
# /api/sentiment/
class SentimentAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SentimentScore.objects.all()
    serializer_class = SentimentScoreSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['customer__industry', 'calculation_method']
    ordering_fields = ['created_at', 'sentiment_score']
    
    @action(detail=False, methods=['get'])
    def segment_analysis(self, request):
        """Get sentiment analysis by industry segment"""
        segments = SegmentSentiment.objects.all()
        
        # Apply time range filtering
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            segments = segments.filter(window_start__gte=start_date)
        if end_date:
            segments = segments.filter(window_end__lte=end_date)
        
        serializer = SegmentSentimentSerializer(segments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overall_metrics(self, request):
        """Get overall product sentiment metrics"""
        overall = OverallSentiment.objects.all()
        
        # Apply time range filtering
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            overall = overall.filter(window_start__gte=start_date)
        if end_date:
            overall = overall.filter(window_end__lte=end_date)
        
        serializer = OverallSentimentSerializer(overall, many=True)
        return Response(serializer.data)
```

### GraphQL Schema

```python
import graphene
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphene import relay

class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        fields = '__all__'
        interfaces = (relay.Node,)
        filter_fields = {
            'industry': ['exact', 'icontains'],
            'company_name': ['exact', 'icontains'],
            'city': ['exact', 'icontains'],
            'state': ['exact', 'icontains'],
        }

class SentimentScoreType(DjangoObjectType):
    class Meta:
        model = SentimentScore
        fields = '__all__'
        interfaces = (relay.Node,)
        filter_fields = {
            'customer__industry': ['exact'],
            'sentiment_score': ['gte', 'lte'],
            'created_at': ['gte', 'lte'],
        }

class SegmentSentimentType(DjangoObjectType):
    class Meta:
        model = SegmentSentiment
        fields = '__all__'
        interfaces = (relay.Node,)

class OverallSentimentType(DjangoObjectType):
    class Meta:
        model = OverallSentiment
        fields = '__all__'
        interfaces = (relay.Node,)

# Input types for time range filtering
class TimeRangeInput(graphene.InputObjectType):
    start_date = graphene.DateTime()
    end_date = graphene.DateTime()

class Query(graphene.ObjectType):
    # Basic node queries
    customer = relay.Node.Field(CustomerType)
    sentiment_score = relay.Node.Field(SentimentScoreType)
    
    # Connection queries with filtering
    customers = DjangoFilterConnectionField(CustomerType)
    sentiment_scores = DjangoFilterConnectionField(SentimentScoreType)
    segment_sentiments = DjangoFilterConnectionField(SegmentSentimentType)
    overall_sentiments = DjangoFilterConnectionField(OverallSentimentType)
    
    # Custom queries for dashboard
    customer_sentiment_history = graphene.List(
        SentimentScoreType,
        customer_id=graphene.ID(required=True),
        time_range=TimeRangeInput()
    )
    
    industry_sentiment_comparison = graphene.List(
        SegmentSentimentType,
        industries=graphene.List(graphene.String),
        time_range=TimeRangeInput()
    )
    
    sentiment_trends = graphene.List(
        OverallSentimentType,
        time_range=TimeRangeInput()
    )
    
    def resolve_customer_sentiment_history(self, info, customer_id, time_range=None):
        queryset = SentimentScore.objects.filter(customer_id=customer_id)
        
        if time_range:
            if time_range.start_date:
                queryset = queryset.filter(window_start__gte=time_range.start_date)
            if time_range.end_date:
                queryset = queryset.filter(window_end__lte=time_range.end_date)
        
        return queryset.order_by('window_start')
    
    def resolve_industry_sentiment_comparison(self, info, industries=None, time_range=None):
        queryset = SegmentSentiment.objects.all()
        
        if industries:
            queryset = queryset.filter(industry__in=industries)
        
        if time_range:
            if time_range.start_date:
                queryset = queryset.filter(window_start__gte=time_range.start_date)
            if time_range.end_date:
                queryset = queryset.filter(window_end__lte=time_range.end_date)
        
        return queryset.order_by('industry', 'window_start')
    
    def resolve_sentiment_trends(self, info, time_range=None):
        queryset = OverallSentiment.objects.all()
        
        if time_range:
            if time_range.start_date:
                queryset = queryset.filter(window_start__gte=time_range.start_date)
            if time_range.end_date:
                queryset = queryset.filter(window_end__lte=time_range.end_date)
        
        return queryset.order_by('window_start')

schema = graphene.Schema(query=Query)
```

## Phased Development Plan

### Phase 1: Core Infrastructure (Week 1)
**Deliverables:**
- [ ] Django project setup with proper app structure
- [ ] Database models and migrations
- [ ] External PostgreSQL connection configuration
- [ ] Basic Django admin interface
- [ ] Initial data sync capability

**Tasks:**
1. Create Django project: `sentiment_analysis`
2. Create apps: `sentiment_api`, `jobs`, `config`
3. Implement all database models
4. Configure multi-database setup
5. Create admin interfaces for all models
6. Test external database connectivity

### Phase 2: Background Processing (Week 2)
**Deliverables:**
- [ ] Django-RQ setup and configuration
- [ ] Complete data sync job implementation
- [ ] Sentiment calculation algorithms
- [ ] Job scheduling and monitoring
- [ ] Historical data backfill capability

**Tasks:**
1. Install and configure Redis + Django-RQ
2. Implement data sync job with error handling
3. Implement all sentiment calculation methods
4. Create job scheduling system
5. Add logging and monitoring
6. Test with historical data backfill

### Phase 3: API Development (Week 3)
**Deliverables:**
- [ ] Complete REST API with DRF
- [ ] GraphQL API with Graphene-Django
- [ ] API documentation (Swagger + GraphQL Playground)
- [ ] CORS configuration
- [ ] Guest access permissions

**Tasks:**
1. Implement REST API endpoints
2. Create GraphQL schema and resolvers
3. Set up API documentation
4. Configure CORS for frontend integration
5. Implement guest access permissions
6. Add API testing suite

### Phase 4: Advanced Features (Week 4)
**Deliverables:**
- [ ] Segment analysis implementation
- [ ] Overall sentiment calculation
- [ ] Time-range filtering optimization
- [ ] Dashboard data aggregation
- [ ] Performance optimization

**Tasks:**
1. Implement segment analysis jobs
2. Create overall sentiment calculation
3. Optimize time-range queries
4. Add database indexing
5. Implement caching where appropriate
6. Performance testing and optimization

## Technology Stack & Dependencies

### Core Dependencies
```bash
# Core Django
pip install django
pip install djangorestframework
pip install django-cors-headers

# GraphQL
pip install graphene-django

# Background Jobs
pip install django-rq
pip install redis

# Database
pip install psycopg2-binary

# API Documentation
pip install drf-spectacular

# Development Tools
pip install django-debug-toolbar
pip install django-extensions

# Testing
pip install pytest-django
pip install factory-boy
pip install coverage
```

### Project Structure
```
sentiment_analysis/
├── manage.py
├── requirements.txt
├── sentiment_analysis/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── sentiment_api/
│   ├── __init__.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── schema.py
│   ├── admin.py
│   └── migrations/
├── jobs/
│   ├── __init__.py
│   ├── data_sync.py
│   ├── sentiment_calc.py
│   ├── segment_analysis.py
│   └── utils.py
├── config/
│   ├── __init__.py
│   ├── models.py
│   ├── admin.py
│   └── migrations/
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_jobs.py
    ├── test_api.py
    └── test_graphql.py
```

## Configuration & Settings

### Django Settings
```python
# settings.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Applications
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'rest_framework',
    'drf_spectacular',
    'graphene_django',
    'django_rq',
    'corsheaders',
    
    # Local apps
    'sentiment_api',
    'jobs',
    'config',
]

# Database Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    },
    'source_db': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('SOURCE_DB_NAME', 'email_security'),
        'USER': os.environ.get('SOURCE_DB_USER', 'admin'),
        'PASSWORD': os.environ.get('SOURCE_DB_PASSWORD', 'securepass123'),
        'HOST': os.environ.get('SOURCE_DB_HOST', 'localhost'),
        'PORT': os.environ.get('SOURCE_DB_PORT', '9876'),
    }
}

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50
}

# Spectacular (Swagger) Settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'Customer Sentiment Analysis API',
    'DESCRIPTION': 'API for analyzing customer sentiment from FN/FP email reports',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Graphene (GraphQL) Settings
GRAPHENE = {
    'SCHEMA': 'sentiment_api.schema.schema',
    'MIDDLEWARE': [
        'graphene_django.debug.DjangoDebugMiddleware',
    ],
}

# Django-RQ Configuration
RQ_QUEUES = {
    'default': {
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 0,
        'PASSWORD': '',
        'DEFAULT_TIMEOUT': 360,
    },
    'high': {
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 0,
        'PASSWORD': '',
        'DEFAULT_TIMEOUT': 500,
    },
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'sentiment_analysis.log',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'jobs': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

## Testing Strategy

### Test Categories
1. **Unit Tests**: Model methods, utility functions, sentiment algorithms
2. **Integration Tests**: Background job processing, database operations
3. **API Tests**: REST endpoints, GraphQL queries, authentication
4. **Performance Tests**: Query optimization, load testing

### Sample Test Implementation
```python
# tests/test_sentiment_calc.py
import pytest
from django.test import TestCase
from sentiment_api.models import Customer, SyncJob, SentimentScore
from jobs.sentiment_calc import simple_ratio, weighted_average_sentiment

class SentimentCalculationTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            customer_id=1,
            company_name="Test Company",
            industry="Technology"
        )
    
    def test_simple_ratio_calculation(self):
        """Test basic FP/(FN+FP) ratio calculation"""
        # Test case: 20 FN, 80 FP -> sentiment = 0.2 (poor)
        sentiment = simple_ratio(20, 80)
        self.assertAlmostEqual(sentiment, 0.2, places=2)
        
        # Test case: 80 FN, 20 FP -> sentiment = 0.8 (good)
        sentiment = simple_ratio(80, 20)
        self.assertAlmostEqual(sentiment, 0.8, places=2)
        
        # Test case: No data -> neutral sentiment
        sentiment = simple_ratio(0, 0)
        self.assertEqual(sentiment, 0.5)
    
    def test_weighted_average_sentiment(self):
        """Test time-decay weighted average calculation"""
        historical_data = [
            {'timestamp': '2024-01-01 10:00:00', 'fn_count': 10, 'fp_count': 5},
            {'timestamp': '2024-01-01 09:00:00', 'fn_count': 8, 'fp_count': 7},
            {'timestamp': '2024-01-01 08:00:00', 'fn_count': 12, 'fp_count': 3},
        ]
        
        sentiment = weighted_average_sentiment(historical_data)
        self.assertGreater(sentiment, 0.0)
        self.assertLess(sentiment, 1.0)
```

## API Endpoints Summary

### REST API Endpoints
```
# Customer Management
GET    /api/customers/                    # List all customers
GET    /api/customers/{id}/               # Get customer details
GET    /api/customers/{id}/sentiment_history/  # Customer sentiment history

# Sentiment Analysis
GET    /api/sentiment/                    # List sentiment scores
GET    /api/sentiment/segment_analysis/   # Industry segment analysis
GET    /api/sentiment/overall_metrics/    # Overall product metrics

# Configuration (Admin only)
GET    /api/config/database/              # Database configurations
POST   /api/config/database/              # Update database config
GET    /api/config/industry_baselines/    # Industry baselines
POST   /api/config/industry_baselines/    # Update baselines

# Health & Monitoring
GET    /api/health/                       # System health check
GET    /api/jobs/status/                  # Background job status

# Documentation
GET    /api/schema/swagger-ui/            # Swagger UI
GET    /api/schema/redoc/                 # ReDoc UI
GET    /api/schema/                       # OpenAPI schema
```

### GraphQL Queries
```graphql
# Customer Queries
query GetCustomers($industry: String, $sentimentRange: FloatRange) {
  customers(industry: $industry, sentimentRange: $sentimentRange) {
    edges {
      node {
        customerId
        companyName
        industry
        currentSentiment
      }
    }
  }
}

# Sentiment History
query GetCustomerSentimentHistory($customerId: ID!, $timeRange: TimeRangeInput) {
  customerSentimentHistory(customerId: $customerId, timeRange: $timeRange) {
    sentimentScore
    windowStart
    windowEnd
    fnCount
    fpCount
  }
}

# Industry Comparison
query GetIndustrySentimentComparison($industries: [String], $timeRange: TimeRangeInput) {
  industrySentimentComparison(industries: $industries, timeRange: $timeRange) {
    industry
    avgSentimentScore
    totalCustomers
    windowStart
  }
}

# Overall Trends
query GetSentimentTrends($timeRange: TimeRangeInput) {
  sentimentTrends(timeRange: $timeRange) {
    avgSentimentScore
    totalCustomers
    totalFnCount
    totalFpCount
    windowStart
  }
}
```

## Deployment & Operations

### Local Development Setup
```bash
# 1. Clone and setup project
git clone <repository>
cd sentiment_analysis
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup Redis (required for background jobs)
# macOS: brew install redis && brew services start redis
# Ubuntu: sudo apt install redis-server && sudo systemctl start redis
# Windows: Download from https://redis.io/download

# 4. Configure environment
cp .env.example .env
# Edit .env with your PostgreSQL connection details

# 5. Setup database
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic

# 6. Load initial data (optional)
python manage.py loaddata initial_industry_baselines.json

# 7. Start services
# Terminal 1: Django server
python manage.py runserver

# Terminal 2: RQ Worker
python manage.py rqworker default

# Terminal 3: RQ Scheduler (for hourly jobs)
python manage.py rqscheduler
```

### Production Considerations
```python
# Production settings adjustments
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'sentiment_analysis_prod',
        'USER': 'sentiment_user',
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': 'localhost',
        'PORT': '5432',
        'OPTIONS': {
            'MAX_CONNS': 20,
            'CONN_MAX_AGE': 600,
        }
    }
}

# Redis configuration for production
RQ_QUEUES = {
    'default': {
        'HOST': 'redis-server',
        'PORT': 6379,
        'DB': 0,
        'PASSWORD': os.environ.get('REDIS_PASSWORD'),
        'CONNECTION_POOL_KWARGS': {
            'max_connections': 50,
            'retry_on_timeout': True,
        },
    }
}

# Security settings
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

## Performance Optimization

### Database Indexing Strategy
```python
# Add to models.py
class SentimentScore(models.Model):
    # ... existing fields ...
    
    class Meta:
        indexes = [
            models.Index(fields=['customer', 'window_start']),
            models.Index(fields=['window_start', 'window_end']),
            models.Index(fields=['created_at']),
            models.Index(fields=['sentiment_score']),
        ]

class SyncJob(models.Model):
    # ... existing fields ...
    
    class Meta:
        indexes = [
            models.Index(fields=['customer', 'window_start']),
            models.Index(fields=['completed_at']),
        ]
        unique_together = ['customer', 'window_start']
```

### Caching Strategy
```python
# Add to settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Cache frequently accessed data
from django.core.cache import cache

def get_industry_baselines():
    baselines = cache.get('industry_baselines')
    if baselines is None:
        baselines = list(IndustryBaseline.objects.all().values())
        cache.set('industry_baselines', baselines, 3600)  # 1 hour
    return baselines
```

## Monitoring & Logging

### Health Check Endpoint
```python
# sentiment_api/views.py
from django.http import JsonResponse
from django.db import connections
import redis

def health_check(request):
    """System health check endpoint"""
    health_status = {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'services': {}
    }
    
    # Check database connectivity
    try:
        connections['default'].ensure_connection()
        health_status['services']['database'] = 'healthy'
    except Exception as e:
        health_status['services']['database'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # Check Redis connectivity
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        health_status['services']['redis'] = 'healthy'
    except Exception as e:
        health_status['services']['redis'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # Check external database
    try:
        connections['source_db'].ensure_connection()
        health_status['services']['source_database'] = 'healthy'
    except Exception as e:
        health_status['services']['source_database'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'degraded'
    
    return JsonResponse(health_status)
```

## Questions for Confirmation

### 1. Sentiment Algorithm Approach
**Current Recommendation**: Start with weighted average method, make all algorithms configurable via admin

**Options**:
- A) Implement all 4 algorithms initially (simple ratio, weighted average, trend-adjusted, industry-normalized)
- B) Start with weighted average only, add others in Phase 4
- C) Use simple ratio for MVP, enhance later

**Question**: Which approach do you prefer for the initial implementation?

### 2. Background Job Technology
**Current Recommendation**: Django-RQ with Redis

**Options**:
- A) Django-RQ (requires Redis installation)
- B) APScheduler (no external dependencies, but less scalable)
- C) Celery (more complex setup, better for production)

**Question**: Is Redis installation acceptable for your environment, or would you prefer APScheduler?

### 3. GraphQL Implementation Scope
**Current Recommendation**: Full Relay-compliant GraphQL with pagination and filtering

**Options**:
- A) Full Relay implementation with connections, pagination, and complex filtering
- B) Simple GraphQL without Relay features (easier to implement)
- C) REST-only initially, add GraphQL in Phase 4

**Question**: Do you need the full GraphQL features for dashboard requirements, or would a simpler approach suffice?

### 4. Industry Baseline Management
**Current Recommendation**: Admin-configurable from the start

**Options**:
- A) Admin-configurable industry baselines with default values
- B) Hardcoded baselines initially, make configurable later
- C) No industry normalization initially

**Question**: Should industry baselines be configurable from the start, or can we hardcode initial values?

### 5. Historical Data Processing
**Current Recommendation**: Process all 10 days of historical data on first run

**Options**:
- A) Full historical backfill on first run (may take time)
- B) Process only recent data initially, backfill gradually
- C) Start fresh without historical data

**Question**: How important is processing all historical data immediately vs. gradual backfill?

## Final Recommendations

Based on the analysis and POC requirements, I recommend:

1. **Start with Phase 1 immediately** - Core infrastructure is well-defined and ready for implementation
2. **Use Django-RQ with Redis** - Best balance of simplicity and scalability for POC
3. **Implement weighted average sentiment algorithm first** - Most sophisticated yet practical approach
4. **Full GraphQL implementation** - Required for interactive dashboard capabilities
5. **Admin-configurable baselines** - Provides flexibility without hardcoding business logic

## Next Steps

1. **Confirm approach preferences** by answering the questions above
2. **Begin Phase 1 implementation** - Django project setup and models
3. **Set up development environment** - Redis, PostgreSQL connection testing
4. **Create initial migrations** and admin interfaces
5. **Test external database connectivity** with sample data

The planning is complete and comprehensive. All major system components are designed, technology choices are justified, and the implementation path is clear. The phased approach allows for iterative development while ensuring core functionality is delivered quickly.

**Ready to proceed with implementation once approach questions are confirmed.**
