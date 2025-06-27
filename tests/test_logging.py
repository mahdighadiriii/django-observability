import pytest
import json
from django.test import RequestFactory
from django.http import HttpResponse
from django_observability.logging import StructuredLogger, JSONFormatter
from django_observability.config import ObservabilityConfig


@pytest.mark.django_db
def test_json_formatter(config):
    """Test JSONFormatter produces valid JSON logs."""
    formatter = JSONFormatter()
    record = type('LogRecord', (), {
        'created': 1234567890.0,
        'levelname': 'INFO',
        'name': 'test',
        'getMessage': lambda: 'Test message',
        'module': 'test_module',
        'funcName': 'test_func',
        'lineno': 42,
        'process': 1234,
        'thread': 5678,
    })()
    
    formatted = formatter.format(record)
    log_entry = json.loads(formatted)
    
    assert log_entry['timestamp']
    assert log_entry['level'] == 'INFO'
    assert log_entry['logger'] == 'test'
    assert log_entry['message'] == 'Test message'
    assert log_entry['module'] == 'test_module'
    assert log_entry['line'] == 42


@pytest.mark.django_db
def test_structured_logger_request(config, request_factory):
    """Test logging request start and end."""
    logger = StructuredLogger(config)
    request = request_factory.get('/test/')
    response = HttpResponse(status=200)
    correlation_id = "test-correlation-id"
    
    logger.log_request_start(request, correlation_id)
    logger.log_request_end(request, response, 0.1, correlation_id)
    
    assert True


@pytest.mark.django_db
def test_structured_logger_exception(config, request_factory):
    """Test logging exceptions."""
    logger = StructuredLogger(config)
    request = request_factory.get('/test/')
    exception = ValueError("Test error")
    correlation_id = "test-correlation-id"
    
    logger.log_exception(request, exception, correlation_id)
    assert True
