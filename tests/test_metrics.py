from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse

from django_observability.metrics import MetricsCollector


@pytest.mark.django_db
def test_metrics_collector_initialization(config):
    """Test MetricsCollector initialization."""
    collector = MetricsCollector(config)
    assert collector.is_available()
    assert collector._initialized
    assert collector.registry is not None


@pytest.mark.django_db
def test_metrics_collector_no_prometheus(config):
    """Test MetricsCollector when prometheus_client is not available."""
    with patch("django_observability.metrics.PROMETHEUS_AVAILABLE", False):
        with patch("django_observability.metrics.logger") as mock_logger:
            collector = MetricsCollector(config)
            assert not collector.is_available()
            assert not collector._initialized
            mock_logger.warning.assert_called_with(
                "Prometheus client not available. Install with: pip install prometheus-client"
            )


@pytest.mark.django_db
def test_record_request_duration(request_factory, config):
    """Test recording request duration metrics."""
    collector = MetricsCollector(config)
    request = request_factory.get("/test/")
    response = HttpResponse(status=200, content=b"test response")

    collector.increment_request_counter(request)
    collector.record_request_duration(request, response, 0.1)
    collector.increment_response_counter(request, response)

    metrics = collector.get_metrics()
    assert "test_app_http_request_duration_seconds" in metrics
    assert "test_app_http_requests_total" in metrics
    assert "test_app_http_response_size_bytes" in metrics


@pytest.mark.django_db
def test_record_exception(request_factory, config):
    """Test recording exception metrics."""
    collector = MetricsCollector(config)
    request = request_factory.get("/test/")
    exception = ValueError("Test error")

    collector.increment_exception_counter(request, exception)
    metrics = collector.get_metrics()
    assert "test_app_http_exceptions_total" in metrics


@pytest.mark.django_db
def test_custom_metrics(config):
    """Test creating custom metrics."""
    collector = MetricsCollector(config)
    counter = collector.create_custom_counter("test_counter", "Test counter", ["label"])
    histogram = collector.create_custom_histogram(
        "test_histogram", "Test histogram", ["label"]
    )
    gauge = collector.create_custom_gauge("test_gauge", "Test gauge", ["label"])

    assert counter is not None
    assert histogram is not None
    assert gauge is not None


@pytest.mark.django_db
def test_custom_counter_usage(config):
    """Test creating and incrementing a custom counter."""
    collector = MetricsCollector(config)
    counter = collector.create_custom_counter("test_counter", "Test counter", ["label"])
    counter.labels(label="value").inc()
    metrics = collector.get_metrics()
    assert "test_app_test_counter_total" in metrics


@pytest.mark.django_db
def test_instrument_database_error(config):
    """Test database instrumentation error handling."""
    collector = MetricsCollector(config)

    mock_cursor = Mock()
    mock_execute = Mock(side_effect=Exception("DB error"))
    mock_cursor.execute = mock_execute

    with patch("django.db.connection.cursor", return_value=mock_cursor):
        with patch("django_observability.metrics.logger") as mock_logger:
            collector._instrument_database()
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT 1")
            except Exception:
                pass
            assert any(
                "Query failed" in str(call) for call in mock_logger.error.call_args_list
            )
            assert "test_app_django_db_queries_total" in collector.get_metrics()


@pytest.mark.django_db
def test_instrument_cache_error(config):
    """Test cache instrumentation error handling."""
    collector = MetricsCollector(config)
    mock_cache = Mock()
    mock_cache.get.side_effect = Exception("Cache error")

    with patch("django.core.cache.caches", return_value={"default": mock_cache}):
        with patch("django_observability.metrics.logger") as mock_logger:
            collector._instrument_cache()
            original_get = cache.get
            cache.get = mock_cache.get
            try:
                cache.get("test_key")
            except Exception:
                pass
            finally:
                cache.get = original_get
            assert any(
                "Failed to record cache operation" in str(call)
                for call in mock_logger.error.call_args_list
            )
            assert "test_app_django_cache_operations_total" in collector.get_metrics()


@pytest.mark.django_db
def test_record_db_query(config):
    """Test recording database query metrics."""
    collector = MetricsCollector(config)
    collector.record_db_query(db_alias="default", query_type="SELECT", duration=0.05)
    metrics = collector.get_metrics()
    assert "test_app_django_db_queries_total" in metrics
    assert "test_app_django_db_query_duration_seconds" in metrics


@pytest.mark.django_db
def test_record_cache_operation(config):
    """Test recording cache operation metrics."""
    collector = MetricsCollector(config)
    collector.record_cache_operation(
        cache_name="default", operation="get", result="hit"
    )
    metrics = collector.get_metrics()
    assert "test_app_django_cache_operations_total" in metrics


@pytest.mark.django_db
def test_get_endpoint_label(request_factory, config):
    """Test endpoint label generation."""
    collector = MetricsCollector(config)
    request = request_factory.get("/api/users/123/")
    assert collector._get_endpoint_label(request) == "api/users/{id}/"


@pytest.mark.django_db
def test_get_request_size(request_factory, config):
    """Test request size calculation."""
    collector = MetricsCollector(config)
    request = request_factory.post(
        "/test/",
        data={"key": "value"},
        content_type="application/x-www-form-urlencoded",
    )
    request.META["CONTENT_LENGTH"] = "10"
    assert collector._get_request_size(request) == 10


@pytest.mark.django_db
def test_get_response_size(config):
    """Test response size calculation."""
    collector = MetricsCollector(config)
    response = HttpResponse(content=b"test response")
    assert collector._get_response_size(response) == len(b"test response")


@pytest.mark.django_db
def test_instrument_database_success(config):
    """Test successful database instrumentation."""
    collector = MetricsCollector(config)

    mock_cursor = Mock()
    mock_execute = Mock(return_value="result")
    mock_cursor.execute = mock_execute

    with patch("django.db.connection.cursor", return_value=mock_cursor):
        with patch("django_observability.metrics.logger") as mock_logger:
            with patch("time.time", side_effect=[1000.0, 1000.1]):
                collector._instrument_database()
                cursor = connection.cursor()
                result = cursor.execute("SELECT 1")
                assert result == "result"
                debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
                assert any("Executing query" in call for call in debug_calls)
                assert any("Query completed" in call for call in debug_calls)
                assert "test_app_django_db_queries_total" in collector.get_metrics()


@pytest.mark.django_db
def test_instrument_cache_success(config):
    """Test successful cache instrumentation."""
    collector = MetricsCollector(config)
    mock_cache = Mock()
    mock_cache.get.return_value = "value"

    with patch("django.core.cache.caches", return_value={"default": mock_cache}):
        with patch("django_observability.metrics.logger") as mock_logger:
            with patch("time.time", side_effect=[1000.0, 1000.1]):
                collector._instrument_cache()
                original_get = cache.get
                cache.get = mock_cache.get
                try:
                    result = cache.get("test_key")
                    assert result == "value"
                    debug_calls = [
                        str(call) for call in mock_logger.debug.call_args_list
                    ]
                    assert any("Cache get completed" in call for call in debug_calls)
                    assert (
                        "test_app_django_cache_operations_total"
                        in collector.get_metrics()
                    )
                finally:
                    cache.get = original_get


@pytest.mark.django_db
def test_instrument_cache_get_many(config):
    """Test cache get_many instrumentation."""
    collector = MetricsCollector(config)
    mock_cache = Mock()
    mock_cache.get_many.return_value = {"key1": "value1", "key2": "value2"}

    with patch("django.core.cache.caches", return_value={"default": mock_cache}):
        with patch("django_observability.metrics.logger") as mock_logger:
            with patch("time.time", side_effect=[1000.0, 1000.1]):
                collector._instrument_cache()
                original_get_many = cache.get_many
                cache.get_many = mock_cache.get_many
                try:
                    result = cache.get_many(["key1", "key2"])
                    assert result == {"key1": "value1", "key2": "value2"}
                    debug_calls = [
                        str(call) for call in mock_logger.debug.call_args_list
                    ]
                    assert any(
                        "Cache get_many completed" in call for call in debug_calls
                    )
                    assert (
                        "test_app_django_cache_operations_total"
                        in collector.get_metrics()
                    )
                finally:
                    cache.get_many = original_get_many


@pytest.mark.django_db
def test_instrument_cache_set(config):
    """Test cache set instrumentation."""
    collector = MetricsCollector(config)
    mock_cache = Mock()
    mock_cache.set.return_value = None

    with patch("django.core.cache.caches", return_value={"default": mock_cache}):
        with patch("django_observability.metrics.logger") as mock_logger:
            with patch("time.time", side_effect=[1000.0, 1000.1]):
                collector._instrument_cache()
                original_set = cache.set
                cache.set = mock_cache.set
                try:
                    result = cache.set("test_key", "test_value")
                    assert result is None
                    debug_calls = [
                        str(call) for call in mock_logger.debug.call_args_list
                    ]
                    assert any("Cache set completed" in call for call in debug_calls)
                    assert (
                        "test_app_django_cache_operations_total"
                        in collector.get_metrics()
                    )
                finally:
                    cache.set = original_set


@pytest.mark.django_db
def test_custom_histogram_error(config):
    """Test error handling in create_custom_histogram."""
    collector = MetricsCollector(config)
    with patch("prometheus_client.Histogram", side_effect=Exception("Histogram error")):
        with patch("django_observability.metrics.logger") as mock_logger:
            result = collector.create_custom_histogram(
                "test_histogram", "Test histogram", ["label"]
            )
            assert result is None
            mock_logger.error.assert_called_once_with(
                "Failed to create custom histogram test_app_test_histogram: Histogram error",
                exc_info=True,
            )


@pytest.mark.django_db
def test_custom_counter_error(config):
    """Test error handling in create_custom_counter."""
    collector = MetricsCollector(config)
    with patch("prometheus_client.Counter", side_effect=Exception("Counter error")):
        with patch("django_observability.metrics.logger") as mock_logger:
            result = collector.create_custom_counter(
                "test_counter", "Test counter", ["label"]
            )
            assert result is None
            mock_logger.error.assert_called_once_with(
                "Failed to create custom counter test_app_test_counter_total: Counter error",
                exc_info=True,
            )


@pytest.mark.django_db
def test_custom_gauge_error(config):
    """Test error handling in create_custom_gauge."""
    collector = MetricsCollector(config)
    with patch("prometheus_client.Gauge", side_effect=Exception("Gauge error")):
        with patch("django_observability.metrics.logger") as mock_logger:
            result = collector.create_custom_gauge(
                "test_gauge", "Test gauge", ["label"]
            )
            assert result is None
            mock_logger.error.assert_called_once_with(
                "Failed to create custom gauge test_app_test_gauge: Gauge error",
                exc_info=True,
            )


@pytest.mark.django_db
def test_record_db_query_error(config):
    """Test error handling in record_db_query."""
    collector = MetricsCollector(config)
    with patch.object(
        collector, "django_db_queries_total", side_effect=Exception("Metric error")
    ):
        with patch("django_observability.metrics.logger") as mock_logger:
            collector.record_db_query(
                db_alias="default", query_type="SELECT", duration=0.05
            )
            assert any(
                "Failed to record DB query metrics" in str(call)
                for call in mock_logger.error.call_args_list
            )


@pytest.mark.django_db
def test_record_request_duration_error(config, request_factory):
    """Test error handling in record_request_duration."""
    collector = MetricsCollector(config)
    request = request_factory.get("/test/")
    response = HttpResponse(status=500)

    with patch.object(
        collector, "_get_endpoint_label", side_effect=Exception("Label error")
    ):
        with patch("django_observability.metrics.logger") as mock_logger:
            collector.record_request_duration(request, response, 0.1)
            assert any(
                "Failed to record request duration" in str(call)
                for call in mock_logger.error.call_args_list
            )
