import pytest
from django.http import HttpResponse

from django_observability.logging import JSONFormatter, StructuredLogger


@pytest.mark.django_db
def test_json_formatter(config):
    """Test JSONFormatter produces valid JSON logs."""
    formatter = JSONFormatter()
    record = type(
        "LogRecord",
        (),
        {
            "created": 1234567890.0,
            "levelname": "INFO",
            "name": "test",
            "getMessage": lambda self: "Test message",
            "module": "test_module",
            "funcName": "test_func",
            "lineno": 42,
            "process": 1234,
            "thread": 5678,
            "exc_info": None,
        },
    )()

    formatted = formatter.format(record)
    assert '"message": "Test message"' in formatted
    assert '"level": "INFO"' in formatted
    assert '"module": "test_module"' in formatted
    assert '"timestamp": "2009-02-13T23:31:30+00:00"' in formatted


@pytest.mark.django_db
def test_json_formatter_with_exception(config):
    """Test JSONFormatter with exception info."""
    formatter = JSONFormatter()
    record = type(
        "LogRecord",
        (),
        {
            "created": 1234567890.0,
            "levelname": "ERROR",
            "name": "test",
            "getMessage": lambda self: "Error message",
            "module": "test_module",
            "funcName": "test_func",
            "lineno": 42,
            "process": 1234,
            "thread": 5678,
            "exc_info": (ValueError, ValueError("Test error"), None),
        },
    )()

    formatted = formatter.format(record)
    assert '"message": "Error message"' in formatted
    assert '"exception": {"type": "ValueError", "message": "Test error"' in formatted


@pytest.mark.django_db
def test_structured_logger_request(config, request_factory):
    """Test

    structured logger for request logging."""
    logger = StructuredLogger(config)
    request = request_factory.get("/test/")
    correlation_id = "test-correlation-id"
    logger.log_request_start(request, correlation_id)
    logger.log_request_end(request, HttpResponse(status=200), 0.1, correlation_id)


@pytest.mark.django_db
def test_structured_logger_exception(config, request_factory):
    """Test structured logger for exception logging."""
    logger = StructuredLogger(config)
    request = request_factory.get("/test/")
    correlation_id = "test-correlation-id"
    exception = ValueError("Test error")
    logger.log_exception(request, exception, correlation_id)
