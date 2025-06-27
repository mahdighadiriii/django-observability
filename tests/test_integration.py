import pytest
from django.test import RequestFactory
from django.http import HttpResponse
from django_observability.middleware import ObservabilityMiddleware
from django_observability.config import ObservabilityConfig


@pytest.mark.django_db
def test_full_request_cycle(request_factory, config):
    """Test full request-response cycle with all components."""
    def get_response(request):
        return HttpResponse(status=200)
    
    middleware = ObservabilityMiddleware(get_response)
    request = request_factory.get('/test/')
    
    middleware.process_request(request)
    response = get_response(request)
    response = middleware.process_response(request, response)
    
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    assert hasattr(request, 'observability_correlation_id')
    assert hasattr(request, 'observability_span')
    assert not request.observability_span.is_recording()


@pytest.mark.django_db
def test_exception_handling(request_factory, config):
    """Test exception handling in middleware."""
    def get_response(request):
        raise ValueError("Test error")
    
    middleware = ObservabilityMiddleware(get_response)
    request = request_factory.get('/test/')
    
    middleware.process_request(request)
    response = middleware.process_exception(request, ValueError("Test error"))
    
    assert response is None
    assert hasattr(request, 'observability_correlation_id')
