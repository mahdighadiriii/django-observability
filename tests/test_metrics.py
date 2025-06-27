import pytest
from django.test import RequestFactory
from django.http import HttpResponse
from prometheus_client import CollectorRegistry
from django_observability.metrics import MetricsCollector
from django_observability.config import ObservabilityConfig


@pytest.mark.django_db
def test_metrics_collector_initialization(config):
    """Test MetricsCollector initialization."""
    collector = MetricsCollector(config)
    assert collector.is_available()
    assert collector._initialized
    assert collector.registry is not None


@pytest.mark.django_db
def test_record_request_duration(request_factory, config):
    """Test recording request duration metrics."""
    collector = MetricsCollector(config)
    request = request_factory.get('/test/')
    response = HttpResponse(status=200)
    
    collector.increment_request_counter(request)
    collector.record_request_duration(request, response, 0.1)
    collector.increment_response_counter(request, response)
    
    metrics = collector.get_metrics()
    assert 'django_app_http_request_duration_seconds' in metrics
    assert 'django_app_http_requests_total' in metrics


@pytest.mark.django_db
def test_record_exception(request_factory, config):
    """Test recording exception metrics."""
    collector = MetricsCollector(config)
    request = request_factory.get('/test/')
    exception = ValueError("Test error")
    
    collector.increment_exception_counter(request, exception)
    metrics = collector.get_metrics()
    assert 'django_app_http_exceptions_total' in metrics


@pytest.mark.django_db
def test_custom_metrics(config):
    """Test creating custom metrics."""
    collector = MetricsCollector(config)
    counter = collector.create_custom_counter("test_counter", "Test counter", ["label"])
    histogram = collector.create_custom_histogram("test_histogram", "Test histogram", ["label"])
    gauge = collector.create_custom_gauge("test_gauge", "Test gauge", ["label"])
    
    assert counter is not None
    assert histogram is not None
    assert gauge is not None
