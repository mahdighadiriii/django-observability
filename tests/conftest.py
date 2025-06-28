import pytest
from django.test import RequestFactory
from django.conf import settings
from django_observability.config import ObservabilityConfig, reload_config

def pytest_configure():
    """Configure Django settings before any tests run."""
    settings.configure(
        DEBUG=True,
        ROOT_URLCONF='tests.urls',
        DJANGO_OBSERVABILITY={
            'TRACING_ENABLED': True,
            'METRICS_ENABLED': True,
            'LOGGING_ENABLED': True,
            'ASYNC_ENABLED': True,
            'DEBUG_MODE': True,
            'EXCLUDE_PATHS': ['/health/', '/metrics/'],
        }
    )
    reload_config()  # Reload ObservabilityConfig after settings are configured

@pytest.fixture
def request_factory():
    """Provide a RequestFactory instance."""
    return RequestFactory()

@pytest.fixture
def config():
    """Provide a fresh ObservabilityConfig instance."""
    return reload_config()
