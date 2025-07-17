import pytest
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

from django_observability.tracing import TracingManager


@pytest.mark.django_db
def test_tracing_otlp_failure(config, mocker):
    """Test tracing setup with invalid OTLP endpoint and fallback to ConsoleSpanExporter."""

    # Mock the OTLP exporter to raise an exception during initialization
    mocker.patch(
        "django_observability.tracing.OTLPSpanExporter",
        side_effect=Exception("Invalid endpoint"),
    )

    # Set invalid endpoint in config
    config._config["TRACING_EXPORT_ENDPOINT"] = "invalid://endpoint"

    # Initialize TracingManager
    tracing_manager = TracingManager(config)

    # Ensure tracing manager still initializes (fallback path)
    assert tracing_manager.is_available()

    # Assert fallback to ConsoleSpanExporter
    span_exporter = tracing_manager._span_processor.span_exporter
    assert isinstance(
        span_exporter, ConsoleSpanExporter
    ), f"Expected ConsoleSpanExporter, got {type(span_exporter)}"
