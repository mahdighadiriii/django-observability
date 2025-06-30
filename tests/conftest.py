"""
Pytest configuration and fixtures for django-observability tests.
"""

import os
import pytest
from django.test import RequestFactory
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from django_observability.config import ObservabilityConfig
from django.conf import settings

# Configure minimal Django settings for tests
if not settings.configured:
    settings.configure(
        DEFAULT_CHARSET="utf-8",
        VERSION="1.0.0",
        LOGGING_CONFIG="logging.config.dictConfig",
        LOGGING={
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": "INFO",
            },
        },
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",  # In-memory SQLite for tests
            }
        },
    )


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state between tests."""
    trace._TRACER_PROVIDER = None
    import django_observability.config

    django_observability.config._config_instance = None
    yield
    trace._TRACER_PROVIDER = None
    django_observability.config._config_instance = None


@pytest.fixture
def config():
    """Create a test configuration with proper settings."""
    config = ObservabilityConfig()
    config._config = {
        "TRACING_ENABLED": True,
        "TRACING_SERVICE_NAME": "tests",
        "TRACING_SAMPLE_RATE": 1.0,
        "SAMPLE_RATE": 1.0,
        "TRACING_PROPAGATORS": ["tracecontext", "baggage"],
        "TRACING_EXPORT_ENDPOINT": None,
        "JAEGER_ENDPOINT": None,
        "ZIPKIN_ENDPOINT": None,
        "METRICS_ENABLED": True,
        "METRICS_PREFIX": "test_app",
        "METRICS_LABELS": {},
        "METRICS_HISTOGRAM_BUCKETS": [
            0.005,
            0.01,
            0.025,
            0.05,
            0.075,
            0.1,
            0.25,
            0.5,
            0.75,
            1.0,
            2.5,
            5.0,
            7.5,
            10.0,
        ],
        "LOGGING_ENABLED": True,
        "LOGGING_FORMAT": "json",
        "LOGGING_LEVEL": "INFO",
        "LOGGING_INCLUDE_HEADERS": False,
        "LOGGING_INCLUDE_BODY": False,
        "LOGGING_SENSITIVE_HEADERS": ["authorization", "cookie", "x-api-key"],
        "ENABLED": True,
        "DEBUG_MODE": True,
        "EXCLUDE_PATHS": ["/health/", "/metrics/", "/favicon.ico"],
        "ASYNC_ENABLED": True,
        "ADD_CORRELATION_HEADER": False,
        "INTEGRATE_DB_TRACING": True,
        "INTEGRATE_CACHE_TRACING": True,
        "INTEGRATE_TEMPLATE_TRACING": True,
        "INTEGRATE_REQUESTS_TRACING": True,
    }
    config._initialized = True
    return config


@pytest.fixture
def request_factory():
    """Create a Django request factory."""
    return RequestFactory()


@pytest.fixture
def tracer_provider():
    """Set up a test tracer provider with full sampling."""
    provider = TracerProvider(sampler=TraceIdRatioBased(1.0))
    processor = SimpleSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    return provider


@pytest.fixture
def tracing_manager(config, tracer_provider):
    """Create a TracingManager instance for testing."""
    from django_observability.tracing import TracingManager

    return TracingManager(config)
