import logging
import re
import time
from typing import List, Optional

from django import get_version as django_get_version
from django.conf import settings
from prometheus_client import Counter, Gauge, Histogram, Info

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, HttpResponse

from .config import ObservabilityConfig
from .utils import get_view_name

logger = logging.getLogger("django_observability.metrics")

# Singleton MetricsCollector instance
_metrics_collector_instance = None


def get_metrics_collector(config: ObservabilityConfig) -> "MetricsCollector":
    """Return a singleton MetricsCollector instance."""
    global _metrics_collector_instance
    if _metrics_collector_instance is None:
        _metrics_collector_instance = MetricsCollector(config)
    return _metrics_collector_instance


class MetricsCollector:
    """
    Collects and manages Prometheus metrics for Django applications.

    This class provides:
    - HTTP request/response metrics
    - Database query metrics
    - Django-specific metrics (active users, cache hits, etc.)
    - Custom business metrics
    """

    def __init__(self, config: ObservabilityConfig):
        """
        Initialize the metrics collector.

        Args:
            config: The observability configuration instance
        """
        self.config = config
        self.registry = CollectorRegistry()
        self._initialized = False

        if not PROMETHEUS_AVAILABLE:
            logger.warning(
                "Prometheus client not available. Install with: pip install prometheus-client"
            )
            return

        self._setup_metrics()
        self._setup_instrumentations()
        self._initialized = True
        logger.debug("MetricsCollector initialized")

    def _setup_metrics(self) -> None:
        """Setup all Prometheus metrics."""
        prefix = self.config.get_metrics_prefix()
        default_labels = self.config.get_metrics_labels()

        # HTTP Request Metrics
        self.http_requests_total = Counter(
            name=f"{prefix}_http_requests_total",
            documentation="Total number of HTTP requests",
            labelnames=["method", "endpoint", "status", "view_name"],
            registry=self.registry,
        )

        self.http_request_duration_seconds = Histogram(
            name=f"{prefix}_http_request_duration_seconds",
            documentation="HTTP request duration in seconds",
            labelnames=["method", "endpoint", "status", "view_name"],
            buckets=self.config.get("METRICS_HISTOGRAM_BUCKETS"),
            registry=self.registry,
        )

        self.http_request_size_bytes = Histogram(
            name=f"{prefix}_http_request_size_bytes",
            documentation="HTTP request size in bytes",
            labelnames=["method", "endpoint"],
            registry=self.registry,
        )

        self.http_response_size_bytes = Histogram(
            name=f"{prefix}_http_response_size_bytes",
            documentation="HTTP response size in bytes",
            labelnames=["method", "endpoint", "status"],
            registry=self.registry,
        )

        # Exception Metrics
        self.http_exceptions_total = Counter(
            name=f"{prefix}_http_exceptions_total",
            documentation="Total number of HTTP exceptions",
            labelnames=["method", "endpoint", "exception_type"],
            registry=self.registry,
        )

        # Django-specific Metrics
        self.django_active_requests = Gauge(
            name=f"{prefix}_django_active_requests",
            documentation="Number of active HTTP requests",
            registry=self.registry,
        )

        self.django_db_queries_total = Counter(
            name=f"{prefix}_django_db_queries_total",
            documentation="Total number of database queries",
            labelnames=["db_alias", "query_type"],
            registry=self.registry,
        )

        self.django_db_query_duration_seconds = Histogram(
            name=f"{prefix}_django_db_query_duration_seconds",
            documentation="Database query duration in seconds",
            labelnames=["db_alias", "query_type"],
            registry=self.registry,
        )

        self.django_cache_operations_total = Counter(
            name=f"{prefix}_django_cache_operations_total",
            documentation="Total number of cache operations",
            labelnames=["cache_name", "operation", "result"],
            registry=self.registry,
        )

        # Application Info
        self.django_info = Info(
            name=f"{prefix}_django_info",
            documentation="Django application information",
            registry=self.registry,
        )

        # Set application info
        self.django_info.info(
            {
                "version": getattr(settings, "VERSION", "unknown"),
                "environment": getattr(settings, "ENVIRONMENT", "unknown"),
                "debug": str(settings.DEBUG),
                "django_version": self._get_django_version(),
            }
        )

        logger.info("Prometheus metrics initialized")

    def _get_django_version(self) -> str:
        """Get Django version."""
        try:
            import django

            return django.get_version()
        except:
            return "unknown"

    def _setup_instrumentations(self) -> None:
        """Setup instrumentation for database and cache operations."""
        try:
            if self.config.get("INTEGRATE_DB_TRACING", True):
                self._instrument_database()
            if self.config.get("INTEGRATE_CACHE_TRACING", True):
                self._instrument_cache()
        except Exception as e:
            logger.error(f"Failed to setup metrics instrumentations: {e}")

    def _instrument_database(self) -> None:
        """Instrument database queries for metrics."""
        try:
            original_execute = connection.cursor().execute

            def wrapped_execute(cursor, sql, params=()):
                logger.debug(f"Executing query: {sql}, params={params}")
                start_time = time.time()
                try:
                    result = original_execute(cursor, sql, params)
                    duration = time.time() - start_time
                    query_type = self._get_query_type(sql)
                    logger.debug(
                        f"Query completed: type={query_type}, duration={duration}"
                    )
                    self.record_db_query(
                        db_alias=connection.alias,
                        query_type=query_type,
                        duration=duration,
                    )
                    return result
                except Exception as e:
                    logger.error(f"Query failed: {e}")
                    self.increment_exception_counter(None, e)
                    raise

            import types

            connection.cursor().execute = types.MethodType(
                wrapped_execute, connection.cursor()
            )
            logger.info("Database metrics instrumentation enabled")
        except Exception as e:
            logger.error(f"Failed to record database instrumentation: {e}")

    def _instrument_cache(self) -> None:
        """Instrument cache operations for metrics."""
        try:
            original_get = cache.get
            original_set = cache.set
            original_get_many = cache.get_many

            def wrapped_get(key, *args, **kwargs):
                logger.debug(f"Cache get: key={key}")
                try:
                    start_time = time.time()
                    result = original_get(key, *args, **kwargs)
                    duration = time.time() - start_time
                    self.record_cache_operation(
                        cache_name="default",
                        operation="get",
                        result="hit" if result is not None else "miss",
                    )
                    logger.debug(f"Cache get completed: key={key}, duration={duration}")
                    return result
                except Exception as e:
                    logger.error(f"Failed to record cache operation: {e}")
                    self.record_cache_operation(
                        cache_name="default", operation="get", result="error"
                    )
                    raise

            def wrapped_set(key, value, timeout=None, *args, **kwargs):
                logger.debug(f"Cache set: key={key}")
                try:
                    start_time = time.time()
                    result = original_set(key, value, timeout, *args, **kwargs)
                    duration = time.time() - start_time
                    self.record_cache_operation(
                        cache_name="default", operation="set", result="success"
                    )
                    logger.debug(f"Cache set completed: key={key}, duration={duration}")
                    return result
                except Exception as e:
                    logger.error(f"Failed to record cache operation: {e}")
                    self.record_cache_operation(
                        cache_name="default", operation="set", result="error"
                    )
                    raise

            def wrapped_get_many(keys, *args, **kwargs):
                logger.debug(f"Cache get_many: keys={keys}")
                try:
                    start_time = time.time()
                    result = original_get_many(keys, *args, **kwargs)
                    duration = time.time() - start_time
                    self.record_cache_operation(
                        cache_name="default",
                        operation="get_many",
                        result="hit" if result else "miss",
                    )
                    logger.debug(
                        f"Cache get_many completed: keys={keys}, duration={duration}"
                    )
                    return result
                except Exception as e:
                    logger.error(f"Failed to record cache operation: {e}")
                    self.record_cache_operation(
                        cache_name="default", operation="get_many", result="error"
                    )
                    raise

            cache.get = wrapped_get
            cache.set = wrapped_set
            cache.get_many = wrapped_get_many
            logger.info("Cache metrics instrumentation enabled")
        except Exception as e:
            logger.error(f"Failed to record cache instrumentation: {e}")

    def _get_query_type(self, sql: str) -> str:
        """Determine the type of SQL query."""
        sql = sql.strip().upper()
        if sql.startswith("SELECT"):
            return "SELECT"
        elif sql.startswith("INSERT"):
            return "INSERT"
        elif sql.startswith("UPDATE"):
            return "UPDATE"
        elif sql.startswith("DELETE"):
            return "DELETE"
        return "UNKNOWN"

    def is_available(self) -> bool:
        """Check if metrics collection is available."""
        return PROMETHEUS_AVAILABLE and self._initialized

    def start_request(self, request: HttpRequest) -> None:
        """
        Start tracking a request for metrics.

        Args:
            request: The Django HttpRequest object
        """
        if not self.is_available():
            return
        logger.debug(
            f"MetricsCollector: Starting request {request.method} {request.path}"
        )
        self.increment_request_counter(request)
        self._instrument_database()
        self._instrument_cache()

    def end_request(
        self, request: HttpRequest, response: HttpResponse, duration: float
    ) -> None:
        """
        End tracking a request and record metrics.

        Args:
            request: The Django HttpRequest object
            response: The Django HttpResponse object
            duration: The request duration in seconds
        """
        if not self.is_available():
            return
        logger.debug(
            f"MetricsCollector: Ending request {request.method} {request.path}, status={response.status_code}, duration={duration}"
        )
        self.record_request_duration(request, response, duration)
        self.increment_response_counter(request, response)

    def increment_request_counter(self, request: HttpRequest) -> None:
        """
        Increment the active requests counter.

        Args:
            request: The Django HttpRequest object
        """
        if not self.is_available():
            return

        try:
            self.django_active_requests.inc()
            logger.debug(
                f"Incremented active requests for {request.method} {request.path}"
            )
        except Exception as e:
            logger.error(f"Failed to increment request counter: {e}")

    def record_request_duration(
        self, request: HttpRequest, response: HttpResponse, duration: float
    ) -> None:
        """
        Record HTTP request duration and related metrics.

        Args:
            request: The Django HttpRequest object
            response: The Django HttpResponse object
            duration: The request duration in seconds
        """
        if not self.is_available():
            return

        try:
            method = request.method
            endpoint = self._get_endpoint_label(request)
            status = str(response.status_code)
            view_name = get_view_name(request)

            logger.debug(
                f"Recording duration: method={method}, endpoint={endpoint}, status={status}, view_name={view_name}, duration={duration}"
            )

            self.http_request_duration_seconds.labels(
                method=method, endpoint=endpoint, status=status, view_name=view_name
            ).observe(duration)

            request_size = self._get_request_size(request)
            if request_size > 0:
                self.http_request_size_bytes.labels(
                    method=method, endpoint=endpoint
                ).observe(request_size)

            response_size = self._get_response_size(response)
            if response_size > 0:
                self.http_response_size_bytes.labels(
                    method=method, endpoint=endpoint, status=status
                ).observe(response_size)

        except Exception as e:
            logger.error(f"Failed to record request duration: {e}")

    def increment_response_counter(
        self, request: HttpRequest, response: HttpResponse
    ) -> None:
        """
        Increment HTTP response counter and decrement active requests.

        Args:
            request: The Django HttpRequest object
            response: The Django HttpResponse object
        """
        if not self.is_available():
            return

        try:
            method = request.method
            endpoint = self._get_endpoint_label(request)
            status = str(response.status_code)
            view_name = get_view_name(request)

            logger.debug(
                f"Incrementing response counter: method={method}, endpoint={endpoint}, status={status}, view_name={view_name}"
            )

            self.http_requests_total.labels(
                method=method, endpoint=endpoint, status=status, view_name=view_name
            ).inc()

            self.django_active_requests.dec()
            logger.debug(
                f"Decremented active requests for {request.method} {request.path}"
            )

        except Exception as e:
            logger.error(f"Failed to increment response counter: {e}")

    def increment_exception_counter(
        self, request: Optional[HttpRequest], exception: Exception
    ) -> None:
        """
        Increment exception counter.

        Args:
            request: The Django HttpRequest object (optional)
            exception: The exception that occurred
        """
        if not self.is_available():
            return

        try:
            method = request.method if request else "UNKNOWN"
            endpoint = self._get_endpoint_label(request) if request else "unknown"
            exception_type = exception.__class__.__name__

            logger.debug(
                f"Incrementing exception counter: method={method}, endpoint={endpoint}, exception_type={exception_type}"
            )

            self.http_exceptions_total.labels(
                method=method, endpoint=endpoint, exception_type=exception_type
            ).inc()

            if request:
                self.django_active_requests.dec()

        except Exception as e:
            logger.error(f"Failed to increment exception counter: {e}")

    def record_db_query(self, db_alias: str, query_type: str, duration: float) -> None:
        """
        Record database query metrics.

        Args:
            db_alias: The database alias
            query_type: The type of query (SELECT, INSERT, UPDATE, DELETE)
            duration: The query duration in seconds
        """
        if not self.is_available():
            return

        try:
            logger.debug(
                f"Recording DB query: db_alias={db_alias}, query_type={query_type}, duration={duration}"
            )
            self.django_db_queries_total.labels(
                db_alias=db_alias, query_type=query_type
            ).inc()

            self.django_db_query_duration_seconds.labels(
                db_alias=db_alias, query_type=query_type
            ).observe(duration)

        except Exception as e:
            logger.error(f"Failed to record DB query metrics: {e}")

    def record_cache_operation(
        self, cache_name: str, operation: str, result: str
    ) -> None:
        """
        Record cache operation metrics.

        Args:
            cache_name: The cache name/alias
            operation: The operation type (get, set, delete, etc.)
            result: The result (hit, miss, success, error)
        """
        if not self.is_available():
            return

        try:
            logger.debug(
                f"Recording cache operation: cache_name={cache_name}, operation={operation}, result={result}"
            )
            self.django_cache_operations_total.labels(
                cache_name=cache_name, operation=operation, result=result
            ).inc()

        except Exception as e:
            logger.error(f"Failed to record cache operation metrics: {e}")

    def _get_endpoint_label(self, request: Optional[HttpRequest]) -> str:
        """
        Generate endpoint label for metrics.

        Args:
            request: The Django HttpRequest object (optional)

        Returns:
            The endpoint label
        """
        if not request:
            return "unknown"

        if hasattr(request, "resolver_match") and request.resolver_match:
            url_name = request.resolver_match.url_name
            if url_name:
                return url_name

        path = request.path
        path = re.sub(r"/\d+/", "/{id}/", path)
        path = re.sub(r"/[0-9a-f-]{36}/", "/{uuid}/", path)

        return path.lstrip("/")

    def _get_request_size(self, request: HttpRequest) -> int:
        """Get request content size in bytes."""
        try:
            content_length = request.META.get("CONTENT_LENGTH")
            if content_length:
                return int(content_length)

            if hasattr(request, "body"):
                return len(request.body)

            return 0
        except (ValueError, TypeError):
            return 0

    def _get_response_size(self, response: HttpResponse) -> int:
        """Get response content size in bytes."""
        try:
            if hasattr(response, "content"):
                return len(response.content)
            return 0
        except:
            return 0

    def get_metrics(self) -> str:
        """
        Get all metrics in Prometheus format.

        Returns:
            Metrics in Prometheus text format
        """
        if not self.is_available():
            return ""

        try:
            return generate_latest(self.registry).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to generate metrics: {e}")
            return ""

    def get_metrics_content_type(self) -> str:
        """Get the content type for metrics response."""
        return CONTENT_TYPE_LATEST

    def create_custom_counter(
        self, name: str, documentation: str, labelnames: Optional[List[str]] = None
    ) -> Optional[Counter]:
        """
        Create a custom counter metric.

        Args:
            name: The metric name
            documentation: The metric documentation
            labelnames: Optional label names

        Returns:
            The created counter, or None if metrics are not available or creation fails
        """
        if not self.is_available():
            return None

        try:
            prefix = self.config.get_metrics_prefix()
            metric_name = f"{prefix}_{name}_total"
            return Counter(
                name=metric_name,
                documentation=documentation,
                labelnames=labelnames or [],
                registry=self.registry,
            )
        except Exception as e:
            logger.error(
                f"Failed to create custom counter {metric_name}: {e}", exc_info=True
            )
            return None

    def create_custom_histogram(
        self,
        name: str,
        documentation: str,
        labelnames: Optional[List[str]] = None,
        buckets: Optional[List[float]] = None,
    ) -> Optional[Histogram]:
        """
        Create a custom histogram metric.

        Args:
            name: The metric name
            documentation: The metric documentation
            labelnames: Optional label names
            buckets: Optional histogram buckets

        Returns:
            The created histogram, or None if metrics are not available or creation fails
        """
        if not self.is_available():
            return None

        try:
            prefix = self.config.get_metrics_prefix()
            metric_name = f"{prefix}_{name}"
            return Histogram(
                name=metric_name,
                documentation=documentation,
                labelnames=labelnames or [],
                buckets=buckets or self.config.get("METRICS_HISTOGRAM_BUCKETS"),
                registry=self.registry,
            )
        except Exception as e:
            logger.error(
                f"Failed to create custom histogram {metric_name}: {e}", exc_info=True
            )
            return None

    def create_custom_gauge(
        self, name: str, documentation: str, labelnames: Optional[List[str]] = None
    ) -> Optional[Gauge]:
        """
        Create a custom gauge metric.

        Args:
            name: The metric name
            documentation: The metric documentation
            labelnames: Optional label names

        Returns:
            The created gauge, or None if metrics are not available or creation fails
        """
        if not self.is_available():
            return None

        try:
            prefix = self.config.get_metrics_prefix()
            metric_name = f"{prefix}_{name}"
            return Gauge(
                name=metric_name,
                documentation=documentation,
                labelnames=labelnames or [],
                registry=self.registry,
            )
        except Exception as e:
            logger.error(
                f"Failed to create custom gauge {metric_name}: {e}", exc_info=True
            )
            return None


def metrics_view(request: HttpRequest) -> HttpResponse:
    """
    View to expose Prometheus metrics.

    Args:
        request: The Django HttpRequest object

    Returns:
        HttpResponse with Prometheus metrics
    """
    from .config import get_config

    config = get_config()
    collector = get_metrics_collector(config)
    metrics_data = collector.get_metrics()
    return HttpResponse(
        content=metrics_data, content_type=collector.get_metrics_content_type()
    )


django_info = Info(
    "django_app_django_info",
    "Django application information",
    ["debug", "django_version", "environment", "version"],
)


def initialize_metrics():
    django_info.labels(
        debug=str(settings.DEBUG),
        django_version=django_get_version(),
        environment=getattr(settings, "ENVIRONMENT", "development"),
        version=getattr(settings, "VERSION", "1.0.0"),
    ).set(1)
