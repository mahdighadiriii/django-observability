"""
OpenTelemetry Tracing Integration for Django.

This module provides comprehensive distributed tracing capabilities using OpenTelemetry,
including automatic instrumentation of Django requests, database queries, and templates.
"""
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.exporter.zipkin.json import ZipkinExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.trace import SpanAttributes
    from opentelemetry.propagate import extract, inject
    from opentelemetry.trace.status import Status, StatusCode
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False

from django.http import HttpRequest, HttpResponse
from django.conf import settings

from .config import ObservabilityConfig
from .utils import get_client_ip, sanitize_headers


logger = logging.getLogger(__name__)


class TracingManager:
    """
    Manages OpenTelemetry tracing for Django applications.

    This class handles:
    - Tracer provider setup and configuration
    - Span creation and management for HTTP requests
    - Integration with Django's request/response cycle
    - Automatic instrumentation of database and cache operations
    """

    def __init__(self, config: ObservabilityConfig):
        """
        Initialize the tracing manager.

        Args:
            config: The observability configuration instance
        """
        self.config = config
        self.tracer = None
        self._initialized = False

        if not OPENTELEMETRY_AVAILABLE:
            logger.warning(
                "OpenTelemetry not available. Install with: "
                "pip install opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-django"
            )
            return

        self._setup_tracing()
        self._setup_instrumentations()

    def _setup_tracing(self) -> None:
        """Setup OpenTelemetry tracer provider and exporters."""
        try:
            # Create resource with service information
            resource = Resource.create({
                "service.name": self.config.get_service_name(),
                "service.version": getattr(settings, 'VERSION', '1.0.0'),
                "deployment.environment": getattr(settings, 'ENVIRONMENT', 'development'),
            })

            # Create tracer provider with sampling
            from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
            tracer_provider = TracerProvider(
                resource=resource,
                sampler=TraceIdRatioBased(self.config.get_sample_rate())
            )

            # Setup exporters
            self._setup_exporters(tracer_provider)

            # Set the global tracer provider
            trace.set_tracer_provider(tracer_provider)

            # Create tracer
            self.tracer = trace.get_tracer(__name__)

            self._initialized = True
            logger.info(
                "OpenTelemetry tracing initialized",
                extra={
                    "service_name": self.config.get_service_name(),
                    "sample_rate": self.config.get_sample_rate(),
                }
            )

        except Exception as e:
            logger.error("Failed to initialize OpenTelemetry tracing", exc_info=True)
            if self.config.get('DEBUG_MODE', False):
                raise

    def _setup_exporters(self, tracer_provider: TracerProvider) -> None:
        """Setup trace exporters based on configuration."""
        exporters = []

        # OTLP Exporter (preferred)
        otlp_endpoint = self.config.get('TRACING_EXPORT_ENDPOINT')
        if otlp_endpoint:
            try:
                exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                exporters.append(exporter)
                logger.info(f"OTLP exporter configured: {otlp_endpoint}")
            except Exception as e:
                logger.error(f"Failed to setup OTLP exporter: {e}")

        # Jaeger Exporter (fallback)
        jaeger_endpoint = self.config.get('JAEGER_ENDPOINT')
        if jaeger_endpoint and not exporters:
            try:
                parsed_url = urlparse(jaeger_endpoint)
                exporter = JaegerExporter(
                    agent_host_name=parsed_url.hostname,
                    agent_port=parsed_url.port or 14268,
                )
                exporters.append(exporter)
                logger.info(f"Jaeger exporter configured: {jaeger_endpoint}")
            except Exception as e:
                logger.error(f"Failed to setup Jaeger exporter: {e}")

        # Zipkin Exporter (additional fallback)
        zipkin_endpoint = self.config.get('ZIPKIN_ENDPOINT')
        if zipkin_endpoint and not exporters:
            try:
                exporter = ZipkinExporter(endpoint=zipkin_endpoint)
                exporters.append(exporter)
                logger.info(f"Zipkin exporter configured: {zipkin_endpoint}")
            except Exception as e:
                logger.error(f"Failed to setup Zipkin exporter: {e}")

        # Console Exporter (development)
        if self.config.get('DEBUG_MODE', False) or not exporters:
            exporters.append(ConsoleSpanExporter())
            logger.info("Console exporter configured")

        # Add processors for each exporter
        for exporter in exporters:
            processor = BatchSpanProcessor(exporter)
            tracer_provider.add_span_processor(processor)

    def _setup_instrumentations(self) -> None:
        """Setup automatic instrumentation for Django and related libraries."""
        if not self._initialized:
            return

        try:
            # Django instrumentation
            if not DjangoInstrumentor().is_instrumented_by_opentelemetry:
                DjangoInstrumentor().instrument(
                    tracer_provider=trace.get_tracer_provider(),
                    request_hook=self._request_hook,
                    response_hook=self._response_hook
                )
                logger.info("Django auto-instrumentation enabled")

            # Database instrumentation
            if self.config.get('INTEGRATE_DB_TRACING', True):
                try:
                    Psycopg2Instrumentor().instrument()
                    logger.info("Psycopg2 instrumentation enabled")
                except ImportError:
                    logger.warning("Psycopg2 instrumentation not available")

                try:
                    from opentelemetry.instrumentation.dbapi import DatabaseApiIntegration
                    DatabaseApiIntegration(
                        connection,
                        "django.db",
                        "sql",
                        enable_commenter=True,
                        commenter_options={"db_driver": "django"}
                    ).instrument()
                except Exception as e:
                    logger.error(f"Failed to instrument database: {e}")

            # Cache instrumentation
            if self.config.get('INTEGRATE_CACHE_TRACING', True):
                try:
                    RedisInstrumentor().instrument()
                    logger.info("Redis cache instrumentation enabled")
                except ImportError:
                    logger.warning("Redis instrumentation not available")

            # HTTP requests instrumentation
            if self.config.get('INTEGRATE_REQUESTS_TRACING', True):
                try:
                    RequestsInstrumentor().instrument()
                    logger.info("Requests instrumentation enabled")
                except ImportError:
                    logger.warning("Requests instrumentation not available")

        except Exception as e:
            logger.error("Failed to setup instrumentations", exc_info=True)
            if self.config.get('DEBUG_MODE', False):
                raise

    def _request_hook(self, span: trace.Span, request: HttpRequest) -> None:
        """Add custom attributes to request spans."""
        if not span:
            return

        span.set_attributes({
            SpanAttributes.HTTP_METHOD: request.method,
            SpanAttributes.HTTP_URL: request.build_absolute_uri(),
            SpanAttributes.HTTP_SCHEME: request.scheme,
            SpanAttributes.HTTP_HOST: request.get_host(),
            SpanAttributes.NET_PEER_IP: get_client_ip(request),
            "http.user_agent": request.META.get('HTTP_USER_AGENT', ''),
            "http.route": get_view_name(request),
        })

        if self.config.get('LOGGING_INCLUDE_HEADERS', False):
            headers = sanitize_headers(request.META, self.config.get_sensitive_headers())
            for key, value in headers.items():
                span.set_attribute(f"http.header.{key.lower()}", value)

        if hasattr(request, 'user') and request.user.is_authenticated:
            span.set_attributes({
                "user.id": str(request.user.id),
                "user.username": request.user.username,
                "user.is_staff": request.user.is_staff,
                "user.is_superuser": request.user.is_superuser,
            })

    def _response_hook(self, span: trace.Span, request: HttpRequest, response: HttpResponse) -> None:
        """Add custom attributes to response spans."""
        if not span:
            return

        span.set_attributes({
            SpanAttributes.HTTP_STATUS_CODE: response.status_code,
            "http.response_content_length": len(response.content) if hasattr(response, 'content') else 0,
        })

    def start_request_span(self, request: HttpRequest, correlation_id: str) -> Optional[trace.Span]:
        """
        Start a new span for an HTTP request.

        Args:
            request: The Django HttpRequest object
            correlation_id: The correlation ID for the request

        Returns:
            The created span, or None if tracing is not available
        """
        if not self._initialized or not self.tracer:
            return None

        # Extract context from headers for distributed tracing
        carrier = {key: value for key, value in request.META.items() if key.startswith('HTTP_')}
        context = extract(carrier)

        # Start span
        span = self.tracer.start_span(
            name=f"{request.method} {request.path}",
            context=context,
            kind=trace.SpanKind.SERVER,
            attributes={
                SpanAttributes.HTTP_METHOD: request.method,
                SpanAttributes.HTTP_URL: request.build_absolute_uri(),
                SpanAttributes.HTTP_SCHEME: request.scheme,
                SpanAttributes.HTTP_HOST: request.get_host(),
                "http.correlation_id": correlation_id,
            }
        )

        # Activate span context
        trace.set_span_in_context(span, context)

        # Inject context into response headers
        inject(carrier)
        request.observability_carrier = carrier

        return span

    def end_request_span(
        self, 
        span: Optional[trace.Span], 
        request: HttpRequest, 
        response: Optional[HttpResponse], 
        duration: float
    ) -> None:
        """
        End a request span and set final attributes.

        Args:
            span: The span to end
            request: The Django HttpRequest object
            response: The Django HttpResponse object (optional)
            duration: The request duration in seconds
        """
        if not span or not self._initialized:
            return

        try:
            if response:
                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status_code)
                if response.status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR))
                else:
                    span.set_status(Status(StatusCode.OK))

            span.set_attribute("http.duration_ms", duration * 1000)
            span.end()
        except Exception as e:
            logger.error("Failed to end request span", exc_info=True)

    def record_exception(self, span: Optional[trace.Span], exception: Exception) -> None:
        """
        Record an exception in the current span.

        Args:
            span: The span to record the exception in
            exception: The exception to record
        """
        if not span or not self._initialized:
            return

        try:
            span.record_exception(exception)
            span.set_status(Status(StatusCode.ERROR, str(exception)))
        except Exception as e:
            logger.error("Failed to record exception in span", exc_info=True)
