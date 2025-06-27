import pytest
from django.test import RequestFactory
from django.http import HttpResponse
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from django_observability.tracing import TracingManager
from django_observability.config import ObservabilityConfig


@pytest.fixture
def tracer_provider():
    """Set up a test tracer provider."""
    provider = TracerProvider()
    processor = SimpleSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    return provider


@pytest.mark.django_db
def test_tracing_manager_initialization(config, tracer_provider):
    """Test TracingManager initialization."""
    tracing_manager = TracingManager(config)
    assert tracing_manager.tracer is not None
    assert tracing_manager._initialized is True


@pytest.mark.django_db
def test_start_request_span(tracing_manager, request_factory):
    """Test starting a request span."""
    request = request_factory.get('/test/')
    correlation_id = "test-correlation-id"
    
    span = tracing_manager.start_request_span(request, correlation_id)
    assert span is not None
    assert span.is_recording()
    assert span.get_span_context().is_valid
    span.end()


@pytest.mark.django_db
def test_end_request_span(tracing_manager, request_factory):
    """Test ending a request span."""
    request = request_factory.get('/test/')
    response = HttpResponse(status=200)
    correlation_id = "test-correlation-id"
    
    span = tracing_manager.start_request_span(request, correlation_id)
    tracing_manager.end_request_span(span, request, response, 0.1)
    assert not span.is_recording()


@pytest.mark.django_db
def test_record_exception(tracing_manager, request_factory):
    """Test recording an exception in a span."""
    request = request_factory.get('/test/')
    correlation_id = "test-correlation-id"
    
    span = tracing_manager.start_request_span(request, correlation_id)
    exception = ValueError("Test error")
    tracing_manager.record_exception(span, exception)
    assert span.status.status_code == trace.StatusCode.ERROR
    span.end()
