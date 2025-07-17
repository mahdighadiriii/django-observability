import pytest
from django.http import HttpResponse

from django_observability.async_support import async_wrapper
from django_observability.middleware import AsyncObservabilityMiddleware


@pytest.mark.asyncio
async def test_async_wrapper(request_factory):
    """Test async_wrapper handles async and sync get_response."""

    async def async_response(request):
        return HttpResponse(status=200)

    def sync_response(request):
        return HttpResponse(status=200)

    request = request_factory.get("/test/")

    response = await async_wrapper(async_response, request)
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200

    response = await async_wrapper(sync_response, request)
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_async_middleware_excluded_path(request_factory):
    """Test async middleware skips excluded paths."""

    async def get_response(request):
        return HttpResponse(status=200)

    middleware = AsyncObservabilityMiddleware(get_response)
    request = request_factory.get("/health/")

    response = await middleware(request)
    assert isinstance(response, HttpResponse)
    assert not hasattr(request, "observability_correlation_id")
