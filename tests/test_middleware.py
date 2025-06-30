import pytest
from django.http import HttpResponse

from django_observability.middleware import (
    AsyncObservabilityMiddleware,
    ObservabilityMiddleware,
)


@pytest.mark.django_db
def test_middleware_initialization(config):
    """Test middleware initialization."""

    def get_response(request):
        return HttpResponse()

    middleware = ObservabilityMiddleware(get_response, config=config)
    assert middleware.config is config
    assert middleware.tracing_manager is not None
    assert middleware.metrics_collector is not None
    assert middleware.structured_logger is not None


@pytest.mark.django_db
def test_middleware_process_request(request_factory):
    """Test process_request adds correlation ID and starts tracing."""

    def get_response(request):
        return HttpResponse()

    middleware = ObservabilityMiddleware(get_response)
    request = request_factory.get("/test/")

    response = middleware.process_request(request)
    assert response is None
    assert hasattr(request, "observability_correlation_id")
    assert hasattr(request, "observability_start_time")
    assert hasattr(request, "observability_span")


@pytest.mark.django_db
def test_middleware_process_response(request_factory):
    """Test process_response records metrics and ends tracing."""

    def get_response(request):
        return HttpResponse(status=200)

    middleware = ObservabilityMiddleware(get_response)
    request = request_factory.get("/test/")
    middleware.process_request(request)
    response = HttpResponse(status=200)

    result = middleware.process_response(request, response)
    assert isinstance(result, HttpResponse)
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_async_middleware(request_factory):
    """Test async middleware processing."""

    async def get_response(request):
        return HttpResponse(status=200)

    middleware = AsyncObservabilityMiddleware(get_response)
    request = request_factory.get("/test/")

    response = await middleware(request)
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    assert hasattr(request, "observability_correlation_id")
