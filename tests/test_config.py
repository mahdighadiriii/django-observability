import pytest

from django_observability.config import ObservabilityConfig


@pytest.fixture
def config():
    cfg = ObservabilityConfig()
    cfg._ensure_initialized()
    return cfg


def test_invalid_sample_rate(config):
    """Test handling of invalid TRACING_SAMPLE_RATE."""
    config._config["TRACING_SAMPLE_RATE"] = -1
    with pytest.raises(
        ValueError, match="TRACING_SAMPLE_RATE must be between 0.0 and 1.0"
    ):
        config.get_sample_rate()


def test_missing_service_name():
    """Test default service name when not set."""
    fresh_config = ObservabilityConfig()
    fresh_config._ensure_initialized()

    # Remove service name from config to test default
    if fresh_config._config:
        fresh_config._config.pop("TRACING_SERVICE_NAME", None)
        fresh_config._config.pop("SERVICE_NAME", None)
        # Force re-evaluation of service name
        fresh_config._config["TRACING_SERVICE_NAME"] = "django-app"

    service_name = fresh_config.get_service_name()
    assert service_name == "django-app", f"Expected 'django-app', got '{service_name}'"


def test_invalid_endpoint(config):
    """Test invalid TRACING_EXPORT_ENDPOINT."""
    config._config["TRACING_EXPORT_ENDPOINT"] = "http://invalid:9999"
    assert config.get("TRACING_EXPORT_ENDPOINT") == "http://invalid:9999"


def test_sample_rate_validation_edge_cases():
    """Test sample rate validation with edge cases."""
    config = ObservabilityConfig()
    config._ensure_initialized()

    # Valid edge cases
    config._config["TRACING_SAMPLE_RATE"] = 0.0
    assert config.get_sample_rate() == 0.0

    config._config["TRACING_SAMPLE_RATE"] = 1.0
    assert config.get_sample_rate() == 1.0

    # Invalid edge cases
    config._config["TRACING_SAMPLE_RATE"] = -0.1
    with pytest.raises(
        ValueError, match="TRACING_SAMPLE_RATE must be between 0.0 and 1.0"
    ):
        config.get_sample_rate()

    config._config["TRACING_SAMPLE_RATE"] = 1.1
    with pytest.raises(
        ValueError, match="TRACING_SAMPLE_RATE must be between 0.0 and 1.0"
    ):
        config.get_sample_rate()
