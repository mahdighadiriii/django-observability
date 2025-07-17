import logging
import os
from typing import Any

from django.db import connection
from django.template import engines
from opentelemetry import trace
from opentelemetry.semconv.trace import SpanAttributes

from .config import ObservabilityConfig

logger = logging.getLogger(__name__)


class DjangoIntegration:
    """
    Handles Django-specific observability integrations for database, cache, and templates.
    """

    def __init__(self, config: ObservabilityConfig):
        """
        Initialize the Django integration.

        Args:
            config: The observability configuration instance
        """
        self.config = config
        if os.getenv("PYTEST_CURRENT_TEST") and not config.get(
            "ENABLE_TEST_INTEGRATION", False
        ):
            return
        self.tracer = trace.get_tracer(__name__)
        self._setup_integrations()

    def _setup_integrations(self) -> None:
        """Setup Django-specific integrations."""
        if self.config.get("INTEGRATE_DB_TRACING", True):
            self._instrument_database()
        if self.config.get("INTEGRATE_CACHE_TRACING", True):
            self._instrument_cache()
        if self.config.get("INTEGRATE_TEMPLATE_TRACING", True):
            self._instrument_templates()

    def _instrument_database(self) -> None:
        """Instrument database queries for tracing."""
        try:
            from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

            try:
                Psycopg2Instrumentor().instrument()
                logger.info("Database instrumentation enabled")
            except Exception as e:
                logger.error(f"Failed to instrument psycopg2: {e}", exc_info=True)
        except ImportError:
            logger.warning("Psycopg2 instrumentation not available")

        try:
            from opentelemetry.instrumentation.dbapi import DatabaseApiIntegration

            DatabaseApiIntegration(
                connection,
                "django.db",
                "sql",
                enable_commenter=True,
                commenter_options={"db_driver": "django"},
            ).instrument()
            logger.info("Database instrumentation enabled")
        except Exception as e:
            logger.error(f"Failed to instrument database: {e}", exc_info=True)

    def _instrument_cache(self) -> None:
        """Instrument cache operations for tracing."""
        try:
            from opentelemetry.instrumentation.redis import RedisInstrumentor

            RedisInstrumentor().instrument()
            logger.info("Redis cache instrumentation enabled")
        except ImportError:
            logger.warning("Redis instrumentation not available")

    def _instrument_templates(self) -> None:
        """Instrument template rendering for tracing."""
        try:
            for engine in engines.all():
                if hasattr(engine, "engine"):
                    engine.engine = self._wrap_template_engine(engine.engine)
            logger.info("Template instrumentation enabled")
        except Exception as e:
            logger.error(f"Failed to instrument templates: {e}", exc_info=True)

    def _wrap_template_engine(self, engine: Any) -> Any:
        """Wrap template engine to trace rendering."""
        original_render = getattr(engine, "render", None)
        if not original_render:
            return engine

        def wrapped_render(*args, **kwargs):
            with self.tracer.start_as_current_span(
                "template.render",
                attributes={
                    SpanAttributes.CODE_FUNCTION: "render",
                    SpanAttributes.CODE_NAMESPACE: engine.__class__.__name__,
                },
            ) as span:
                result = original_render(*args, **kwargs)
                if "template_name" in kwargs:
                    span.set_attribute("template.name", kwargs["template_name"])
                return result

        engine.render = wrapped_render
        return engine
