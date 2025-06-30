import os
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from django.db import connection
from django.http import HttpResponse

from django_observability import django_integration
from django_observability.config import get_config
from django_observability.middleware import ObservabilityMiddleware


@pytest.mark.django_db
def test_full_request_cycle(request_factory):
    """Test full request-response cycle with all components."""
    config = get_config()
    config.force_reload()

    def get_response(request):
        return HttpResponse(status=200)

    middleware = ObservabilityMiddleware(get_response)
    request = request_factory.get("/test/")

    response = middleware.process_request(request)
    assert response is None

    response = get_response(request)
    response = middleware.process_response(request, response)

    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    assert hasattr(request, "observability_correlation_id")
    assert hasattr(request, "observability_span")


@pytest.mark.django_db
def test_exception_handling(request_factory):
    """Test exception handling in middleware."""
    config = get_config()

    def get_response(request):
        raise ValueError("Test error")

    middleware = ObservabilityMiddleware(get_response)
    request = request_factory.get("/test/")

    middleware.process_request(request)
    response = middleware.process_exception(request, ValueError("Test error"))

    assert response is None
    assert hasattr(request, "observability_correlation_id")


@pytest.mark.django_db
def test_excluded_paths(request_factory):
    """Test that excluded paths are not processed."""
    config = get_config()

    def get_response(request):
        return HttpResponse(status=200)

    middleware = ObservabilityMiddleware(get_response)
    request = request_factory.get("/health/")
    response = middleware.process_request(request)

    assert response is None
    assert not hasattr(request, "observability_correlation_id")


@pytest.mark.django_db
def test_config_integration(request_factory):
    """Test that configuration is properly integrated."""
    config = get_config()

    assert config.is_enabled()
    assert config.is_tracing_enabled()
    assert config.is_metrics_enabled()
    assert config.is_logging_enabled()

    service_name = config.get_service_name()
    assert service_name in [
        "test-app",
        "tests",
        "django-app",
        "example_project",
        "drfp",
    ]

    exclude_paths = config.get_exclude_paths()
    assert "/health/" in exclude_paths
    assert "/metrics/" in exclude_paths

    assert not config.should_trace_request("/health/")
    assert not config.should_trace_request("/metrics/prometheus")
    assert config.should_trace_request("/api/users/")
    assert config.should_trace_request("/test/")


@pytest.mark.django_db
def test_django_integration_init():
    """Test Django integration initialization."""
    assert django_integration.__name__ == "django_observability.django_integration"


@pytest.mark.django_db
def test_django_integration_init_with_pytest_env():
    """Test DjangoIntegration init with PYTEST_CURRENT_TEST env variable."""
    config = get_config()
    config.force_reload()

    with patch.dict(
        os.environ,
        {"PYTEST_CURRENT_TEST": "test", "DJANGO_ENABLE_TEST_INTEGRATION": "False"},
    ):
        with patch.object(config, "get", return_value=False) as mock_config_get:
            with patch("opentelemetry.trace.get_tracer") as mock_tracer:
                integration = django_integration.DjangoIntegration(config)
                mock_tracer.assert_not_called()
                assert integration.config == config
                assert any(
                    call.args == ("ENABLE_TEST_INTEGRATION", False)
                    for call in mock_config_get.call_args_list
                )

    with patch.dict(
        os.environ,
        {"PYTEST_CURRENT_TEST": "test", "DJANGO_ENABLE_TEST_INTEGRATION": "True"},
    ):
        with patch.object(config, "get", return_value=True) as mock_config_get:
            with patch("opentelemetry.trace.get_tracer") as mock_tracer:
                with patch(
                    "opentelemetry.instrumentation.redis.RedisInstrumentor"
                ) as mock_redis:
                    with patch(
                        "opentelemetry.instrumentation.psycopg2.Psycopg2Instrumentor"
                    ) as mock_psycopg:
                        with patch(
                            "opentelemetry.instrumentation.dbapi.DatabaseApiIntegration"
                        ) as mock_dbapi:
                            integration = django_integration.DjangoIntegration(config)
                            mock_tracer.assert_called_once_with(
                                "django_observability.django_integration"
                            )
                            assert integration.config == config
                            assert any(
                                call.args == ("ENABLE_TEST_INTEGRATION", False)
                                for call in mock_config_get.call_args_list
                            )
                            mock_redis().instrument.assert_called_once()
                            mock_psycopg().instrument.assert_called_once()
                            mock_dbapi.assert_called_once()


@pytest.mark.django_db
def test_setup_integrations():
    """Test _setup_integrations with different config settings."""
    config = get_config()
    config.force_reload()

    with patch.dict(
        os.environ,
        {
            "DJANGO_INTEGRATE_DB_TRACING": "True",
            "DJANGO_INTEGRATE_CACHE_TRACING": "True",
            "DJANGO_INTEGRATE_TEMPLATE_TRACING": "True",
        },
    ):
        with patch.object(
            config,
            "get",
            side_effect=lambda key, default: (
                True
                if key
                in [
                    "INTEGRATE_DB_TRACING",
                    "INTEGRATE_CACHE_TRACING",
                    "INTEGRATE_TEMPLATE_TRACING",
                ]
                else default
            ),
        ):
            integration = django_integration.DjangoIntegration(config)
            integration._setup_integrations()

    with patch.dict(
        os.environ,
        {
            "DJANGO_INTEGRATE_DB_TRACING": "False",
            "DJANGO_INTEGRATE_CACHE_TRACING": "False",
            "DJANGO_INTEGRATE_TEMPLATE_TRACING": "False",
        },
    ):
        with patch.object(
            config,
            "get",
            side_effect=lambda key, default: (
                False
                if key
                in [
                    "INTEGRATE_DB_TRACING",
                    "INTEGRATE_CACHE_TRACING",
                    "INTEGRATE_TEMPLATE_TRACING",
                ]
                else default
            ),
        ):
            integration = django_integration.DjangoIntegration(config)
            integration._setup_integrations()


@pytest.mark.django_db
def test_instrument_database_success():
    """Test database instrumentation success cases."""
    config = get_config()
    config.force_reload()
    integration = django_integration.DjangoIntegration(config)

    with patch(
        "opentelemetry.instrumentation.psycopg2.Psycopg2Instrumentor"
    ) as mock_psycopg:
        with patch(
            "opentelemetry.instrumentation.dbapi.DatabaseApiIntegration"
        ) as mock_dbapi:
            with patch("django_observability.django_integration.logger") as mock_logger:
                integration._instrument_database()
                mock_psycopg().instrument.assert_called_once()
                mock_dbapi.assert_called_once_with(
                    connection,
                    "django.db",
                    "sql",
                    enable_commenter=True,
                    commenter_options={"db_driver": "django"},
                )
                mock_logger.info.assert_called_with("Database instrumentation enabled")


@pytest.mark.django_db
def test_instrument_database_failure():
    """Test database instrumentation failure cases."""
    config = get_config()
    config.force_reload()
    integration = django_integration.DjangoIntegration(config)

    with patch(
        "opentelemetry.instrumentation.psycopg2.Psycopg2Instrumentor",
        side_effect=ImportError,
    ):
        with patch("django_observability.django_integration.logger") as mock_logger:
            integration._instrument_database()
            mock_logger.warning.assert_called_once_with(
                "Psycopg2 instrumentation not available"
            )

    with patch(
        "opentelemetry.instrumentation.psycopg2.Psycopg2Instrumentor"
    ) as mock_psycopg:
        with patch(
            "opentelemetry.instrumentation.dbapi.DatabaseApiIntegration"
        ) as mock_dbapi:
            mock_psycopg().instrument.side_effect = Exception("DB error")
            with patch("django_observability.django_integration.logger") as mock_logger:
                integration._instrument_database()
                mock_logger.error.assert_called_with(
                    "Failed to instrument psycopg2: DB error", exc_info=True
                )


@pytest.mark.django_db
def test_instrument_cache():
    """Test cache instrumentation success and failure cases."""
    config = get_config()
    config.force_reload()
    integration = django_integration.DjangoIntegration(config)

    with patch("django_observability.django_integration.logger") as mock_logger:
        integration._instrument_cache()
        mock_logger.info.assert_called_with("Redis cache instrumentation enabled")

    with patch(
        "opentelemetry.instrumentation.redis.RedisInstrumentor", side_effect=ImportError
    ):
        with patch("django_observability.django_integration.logger") as mock_logger:
            integration._instrument_cache()
            mock_logger.warning.assert_called_with(
                "Redis instrumentation not available"
            )


@pytest.mark.django_db
def test_instrument_templates():
    """Test template instrumentation success and failure cases."""
    config = get_config()
    config.force_reload()
    integration = django_integration.DjangoIntegration(config)

    mock_engine = Mock()
    mock_engine.engine = Mock()
    mock_engine.engine.render = Mock(return_value="rendered")

    with patch("django_observability.django_integration.engines") as mock_engines:
        mock_engines.all.return_value = [mock_engine]
        with patch("django_observability.django_integration.logger") as mock_logger:
            integration._instrument_templates()
            mock_logger.info.assert_called_with("Template instrumentation enabled")
            assert mock_engine.engine.render != Mock()

    with patch("django_observability.django_integration.engines") as mock_engines:
        mock_engines.all.side_effect = Exception("Template error")
        with patch("django_observability.django_integration.logger") as mock_logger:
            integration._instrument_templates()
            mock_logger.error.assert_called_with(
                "Failed to instrument templates: Template error", exc_info=True
            )


@pytest.mark.django_db
def test_wrap_template_engine():
    """Test template engine wrapping and tracing."""
    config = get_config()
    config.force_reload()
    with patch.dict(
        os.environ,
        {"PYTEST_CURRENT_TEST": "", "DJANGO_ENABLE_TEST_INTEGRATION": "True"},
    ):
        with patch.object(config, "get", return_value=True):
            integration = django_integration.DjangoIntegration(config)

    mock_engine = Mock()
    mock_engine.render = Mock(return_value="rendered")
    mock_span = Mock()
    mock_tracer = Mock()

    @contextmanager
    def mock_context_manager(*args, **kwargs):
        yield mock_span

    mock_tracer.start_as_current_span = Mock(return_value=mock_context_manager())

    with patch.object(integration, "tracer", mock_tracer):
        wrapped_engine = integration._wrap_template_engine(mock_engine)
        result = wrapped_engine.render(template_name="test_template")
        assert result == "rendered"
        mock_tracer.start_as_current_span.assert_called_with(
            "template.render",
            attributes={
                "code.function": "render",
                "code.namespace": mock_engine.__class__.__name__,
            },
        )
        mock_span.set_attribute.assert_called_with("template.name", "test_template")


@pytest.mark.django_db
def test_wrap_template_engine_no_render():
    """Test _wrap_template_engine when engine has no render method."""
    config = get_config()
    config.force_reload()
    with patch.dict(
        os.environ,
        {"PYTEST_CURRENT_TEST": "", "DJANGO_ENABLE_TEST_INTEGRATION": "True"},
    ):
        with patch.object(config, "get", return_value=True):
            integration = django_integration.DjangoIntegration(config)

    mock_engine = Mock()
    mock_engine.render = None

    with patch("opentelemetry.trace.get_tracer"):
        wrapped_engine = integration._wrap_template_engine(mock_engine)
        assert wrapped_engine == mock_engine
