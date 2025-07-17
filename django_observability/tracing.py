"""
OpenTelemetry Tracing Integration for Django.

This module provides distributed tracing capabilities using OpenTelemetry,
including automatic instrumentation of Django requests.
"""

import logging
from typing import Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("django_observability.tracing")

try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.semconv.trace import SpanAttributes

    OPENTELEMETRY_AVAILABLE = True
    OTLP_AVAILABLE = False
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        OTLP_AVAILABLE = True
    except ImportError as e:
        logger.warning(
            f"OTLPSpanExporter import failed: {str(e)}. Falling back to ConsoleSpanExporter."
        )
    logger.debug(
        "OpenTelemetry imports successful: trace=%s, TracerProvider=%s, BatchSpanProcessor=%s, DjangoInstrumentor=%s, OTLPSpanExporter=%s",
        getattr(trace, "__version__", "unknown"),
        TracerProvider.__module__,
        BatchSpanProcessor.__module__,
        DjangoInstrumentor.__module__,
        "available" if OTLP_AVAILABLE else "not available",
    )
except ImportError as e:
    OPENTELEMETRY_AVAILABLE = False
    OTLP_AVAILABLE = False
    logger.error(
        f"OpenTelemetry import failed: {str(e)}. Ensure opentelemetry-api==1.34.1, opentelemetry-sdk==1.34.1, opentelemetry-instrumentation-django==0.55b1 are installed."
    )

from .config import ObservabilityConfig
from .utils import get_client_ip, get_view_name


class TracingManager:
    """
    Manages OpenTelemetry tracing for Django applications.

    This class handles:
    - Tracer provider setup with OTLP or console exporter
    - Span creation for HTTP requests
    - Django auto-instrumentation
    - Exception recording
    """

    def __init__(self, config: ObservabilityConfig):
        """
        Initialize the tracing manager.

        Args:
            config: The observability configuration instance
        """
        self.config = config
        self.tracer = None
        self._span_processor = None
        self._initialized = False

        if not OPENTELEMETRY_AVAILABLE:
            logger.warning("Tracing disabled: OpenTelemetry not available")
            return

        try:
            self._setup_tracing()
            self._setup_instrumentations()
            self._initialized = True
            logger.info(
                "OpenTelemetry tracing initialized",
                extra={
                    "service_name": self.config.get_service_name(),
                    "sample_rate": self.config.get_sample_rate(),
                    "debug_mode": self.config.get("DEBUG_MODE", False),
                    "version": getattr(settings, "VERSION", "1.0.0"),
                    "environment": getattr(settings, "ENVIRONMENT", "development"),
                },
            )
        except Exception as e:
            logger.error(f"Failed to initialize tracing: {str(e)}", exc_info=True)
            if self.config.get("DEBUG_MODE", False):
                raise

    def _setup_tracing(self) -> None:
        """
        Setup OpenTelemetry tracer provider and exporters.
        """
        # Create resource with service information
        resource = Resource.create(
            {
                "service.name": self.config.get_service_name(),
                "service.version": getattr(settings, "VERSION", "1.0.0"),
                "deployment.environment": getattr(
                    settings, "ENVIRONMENT", "development"
                ),
            }
        )

        # Create tracer provider
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        tracer_provider = TracerProvider(
            resource=resource, sampler=TraceIdRatioBased(self.config.get_sample_rate())
        )

        # Setup exporters
        otlp_endpoint = self.config.get("TRACING_EXPORT_ENDPOINT")
        if otlp_endpoint and OTLP_AVAILABLE:
            try:
                exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                self._span_processor = BatchSpanProcessor(exporter)
                tracer_provider.add_span_processor(self._span_processor)
                logger.info(f"OTLP exporter configured: {otlp_endpoint}")
            except Exception as e:
                logger.error(
                    f"Failed to setup OTLP exporter: {str(e)}. Falling back to ConsoleSpanExporter."
                )
                exporter = ConsoleSpanExporter()
                self._span_processor = BatchSpanProcessor(exporter)
                tracer_provider.add_span_processor(self._span_processor)
                logger.info("ConsoleSpanExporter configured as fallback")
        else:
            exporter = ConsoleSpanExporter()
            self._span_processor = BatchSpanProcessor(exporter)
            tracer_provider.add_span_processor(self._span_processor)
            logger.info("ConsoleSpanExporter configured for development")

        # Set global tracer provider
        trace.set_tracer_provider(tracer_provider)
        self.tracer = trace.get_tracer("django_observability")
        logger.debug(f"Tracer initialized: {self.tracer}")

    def _setup_instrumentations(self) -> None:
        """
        Setup automatic instrumentation for Django.
        """
        if not self._initialized:
            return

        try:
            if not DjangoInstrumentor().is_instrumented_by_opentelemetry:
                DjangoInstrumentor().instrument(
                    tracer_provider=trace.get_tracer_provider(),
                    request_hook=self._request_hook,
                    response_hook=self._response_hook,
                )
                logger.info("Django auto-instrumentation enabled")
        except Exception as e:
            logger.error(
                f"Failed to setup Django instrumentation: {str(e)}", exc_info=True
            )
            if self.config.get("DEBUG_MODE", False):
                raise

    def _request_hook(self, span: trace.Span, request: HttpRequest) -> None:
        """
        Add custom attributes to request spans.

        Args:
            span: The OpenTelemetry span
            request: The Django HttpRequest object
        """
        if not span:
            return

        try:
            span.set_attributes(
                {
                    SpanAttributes.HTTP_METHOD: request.method,
                    SpanAttributes.HTTP_URL: request.build_absolute_uri(),
                    SpanAttributes.HTTP_SCHEME: request.scheme,
                    SpanAttributes.HTTP_HOST: request.get_host(),
                    SpanAttributes.NET_PEER_IP: get_client_ip(request),
                    "http.user_agent": request.META.get("HTTP_USER_AGENT", "unknown"),
                    "http.route": get_view_name(request),
                }
            )
            logger.debug(
                f"Set request attributes for span: {request.method} {request.path}"
            )
        except Exception as e:
            logger.error(f"Failed to set request attributes: {str(e)}")

    def _response_hook(
        self, span: trace.Span, request: HttpRequest, response: HttpResponse
    ) -> None:
        """
        Add custom attributes to response spans.

        Args:
            span: The OpenTelemetry span
            request: The Django HttpRequest object
            response: The Django HttpResponse object
        """
        if not span:
            return

        try:
            span.set_attributes(
                {
                    SpanAttributes.HTTP_STATUS_CODE: response.status_code,
                    "http.response_content_length": (
                        len(response.content) if hasattr(response, "content") else 0
                    ),
                }
            )
            logger.debug(
                f"Set response attributes for span: {request.method} {request.path}, status={response.status_code}"
            )
        except Exception as e:
            logger.error(f"Failed to set response attributes: {str(e)}")

    def is_available(self) -> bool:
        """
        Check if tracing is available and properly initialized.

        Returns:
            True if tracing is available, False otherwise
        """
        return OPENTELEMETRY_AVAILABLE and self._initialized and self.tracer is not None

    def start_request_span(
        self, request: HttpRequest, correlation_id: str
    ) -> Optional[trace.Span]:
        """
        Start a new span for an HTTP request.

        Args:
            request: The Django HttpRequest object
            correlation_id: The correlation ID for the request

        Returns:
            The created span, or None if tracing is not available
        """
        if not self.is_available():
            logger.debug("Cannot start span: tracing not available")
            return None

        try:
            span = self.tracer.start_span(
                name=f"{request.method} {get_view_name(request)}",
                attributes={
                    SpanAttributes.HTTP_METHOD: request.method,
                    SpanAttributes.HTTP_URL: request.build_absolute_uri(),
                    SpanAttributes.HTTP_SCHEME: request.scheme,
                    SpanAttributes.HTTP_HOST: request.get_host(),
                    SpanAttributes.NET_PEER_IP: get_client_ip(request),
                    "http.user_agent": request.META.get("HTTP_USER_AGENT", "unknown"),
                    "http.correlation_id": correlation_id,
                    "http.route": get_view_name(request),
                },
            )
            logger.debug(f"Started span for {request.method} {request.path}: {span}")
            return span
        except Exception as e:
            logger.error(
                f"Failed to start span for {request.method} {request.path}: {str(e)}"
            )
            return None

    def end_request_span(
        self,
        span: Optional[trace.Span],
        request: HttpRequest,
        response: Optional[HttpResponse],
        duration: float,
    ) -> None:
        """
        End a request span and set final attributes.

        Args:
            span: The span to end
            request: The Django HttpRequest object
            response: The Django HttpResponse object (optional)
            duration: The request duration in seconds
        """
        if not self.is_available() or not span:
            logger.debug("Cannot end span: tracing not available or span is None")
            return

        try:
            if response:
                span.set_attribute(
                    SpanAttributes.HTTP_STATUS_CODE, response.status_code
                )
                span.set_attribute(
                    "http.response_content_length",
                    len(response.content) if hasattr(response, "content") else 0,
                )
                if response.status_code >= 400:
                    span.set_status(trace.Status(trace.StatusCode.ERROR))
                else:
                    span.set_status(trace.Status(trace.StatusCode.OK))
            span.set_attribute("http.duration_ms", duration * 1000)
            span.end()
            logger.debug(f"Ended span for {request.method} {request.path}")
            # Force flush spans for console output
            if self._span_processor:
                self._span_processor.force_flush()
                logger.debug("Span processor flushed")
        except Exception as e:
            logger.error(
                f"Failed to end span for {request.method} {request.path}: {str(e)}"
            )

    def record_exception(
        self, span: Optional[trace.Span], exception: Exception
    ) -> None:
        """
        Record an exception in the current span.

        Args:
            span: The span to record the exception in
            exception: The exception to record
        """
        if not self.is_available() or not span:
            logger.debug(
                "Cannot record exception: tracing not available or span is None"
            )
            return

        try:
            span.record_exception(exception)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))
            logger.debug(f"Recorded exception in span: {exception.__class__.__name__}")
            # Force flush spans for console output
            if self._span_processor:
                self._span_processor.force_flush()
                logger.debug("Span processor flushed after exception")
        except Exception as e:
            logger.error(f"Failed to record exception: {str(e)}")
