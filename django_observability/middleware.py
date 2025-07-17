"""
Django Observability Middleware

This middleware provides comprehensive observability for Django applications
including distributed tracing, metrics collection, and structured logging.
"""

import logging
import time
import uuid
from typing import Callable, Optional

from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from .config import get_config
from .exceptions import ObservabilityError
from .logging import StructuredLogger
from .metrics import get_metrics_collector
from .tracing import TracingManager
from .utils import is_excluded_path

logger = logging.getLogger("django_observability")


class ObservabilityMiddleware(MiddlewareMixin):
    """
    Main observability middleware that coordinates tracing, metrics, and logging.

    This middleware supports both sync and async Django applications and provides:
    - Distributed tracing with OpenTelemetry
    - Prometheus metrics collection
    - Structured logging with correlation IDs
    - Request/response timing and metadata
    """

    def __init__(self, get_response: Optional[Callable] = None, config=None):
        """
        Initialize the middleware.

        Args:
            get_response: The next middleware or view function in the chain
        """
        self.config = config or get_config()

        # Check if observability is enabled
        if not self.config.is_enabled():
            logger.info("Django Observability is disabled")
            raise MiddlewareNotUsed("Django Observability is disabled")

        # Initialize components
        self.tracing_manager = (
            TracingManager(self.config) if self.config.is_tracing_enabled() else None
        )
        self.metrics_collector = (
            get_metrics_collector(self.config)
            if self.config.is_metrics_enabled()
            else None
        )
        self.structured_logger = (
            StructuredLogger(self.config) if self.config.is_logging_enabled() else None
        )

        super().__init__(get_response)

        logger.info(
            "Django Observability Middleware initialized",
            extra={
                "tracing_enabled": self.config.is_tracing_enabled(),
                "metrics_enabled": self.config.is_metrics_enabled(),
                "logging_enabled": self.config.is_logging_enabled(),
                "service_name": self.config.get_service_name(),
            },
        )

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process incoming request - start tracing, add correlation ID, log request.

        Args:
            request: The Django HttpRequest object

        Returns:
            None to continue processing, or HttpResponse to short-circuit
        """
        if is_excluded_path(request.path, self.config.get("EXCLUDE_PATHS", [])):
            logger.debug(f"Skipping request due to excluded path: {request.path}")
            return None

        # Add correlation ID to request
        correlation_id = str(uuid.uuid4())
        request.observability_correlation_id = correlation_id
        request.observability_start_time = time.time()

        try:
            logger.debug(
                f"Processing request: {request.method} {request.path}, correlation_id={correlation_id}"
            )
            # Start tracing
            if self.tracing_manager:
                span = self.tracing_manager.start_request_span(request, correlation_id)
                request.observability_span = span

            # Log incoming request
            if self.structured_logger:
                self.structured_logger.log_request_start(request, correlation_id)

            # Increment request counter
            if self.metrics_collector:
                logger.debug(
                    f"Calling start_request for {request.method} {request.path}"
                )
                self.metrics_collector.start_request(request)

        except Exception as e:
            logger.error(
                "Error in ObservabilityMiddleware.process_request",
                exc_info=True,
                extra={"correlation_id": correlation_id},
            )
            if self.config.get("DEBUG_MODE", False):
                raise ObservabilityError(f"Failed to process request: {e}") from e

        return None

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        """
        Process outgoing response - end tracing, record metrics, log response.

        Args:
            request: The Django HttpRequest object
            response: The Django HttpResponse object

        Returns:
            The response object (potentially modified)
        """
        if not hasattr(request, "observability_correlation_id"):
            logger.debug(
                f"No correlation ID for response: {request.method} {request.path}"
            )
            return response

        correlation_id = request.observability_correlation_id

        try:
            # Calculate request duration
            if hasattr(request, "observability_start_time"):
                duration = time.time() - request.observability_start_time
            else:
                duration = 0.0

            logger.debug(
                f"Processing response: {request.method} {request.path}, status={response.status_code}, duration={duration}, correlation_id={correlation_id}"
            )

            # Record metrics
            if self.metrics_collector:
                self.metrics_collector.end_request(request, response, duration)

            # End tracing
            if self.tracing_manager and hasattr(request, "observability_span"):
                self.tracing_manager.end_request_span(
                    request.observability_span, request, response, duration
                )

            # Log response
            if self.structured_logger:
                self.structured_logger.log_request_end(
                    request, response, duration, correlation_id
                )

            if self.config.get("ADD_CORRELATION_HEADER", False):
                response["X-Correlation-ID"] = correlation_id

        except Exception as e:
            # Log error but don't fail the response
            logger.error(
                "Error in ObservabilityMiddleware.process_response",
                exc_info=True,
                extra={"correlation_id": correlation_id},
            )
            if self.config.get("DEBUG_MODE", False):
                raise ObservabilityError(f"Failed to process response: {e}") from e

        return response

    def process_exception(
        self, request: HttpRequest, exception: Exception
    ) -> Optional[HttpResponse]:
        """
        Process unhandled exceptions - record in traces, metrics, and logs.

        Args:
            request: The Django HttpRequest object
            exception: The unhandled exception

        Returns:
            None (don't handle the exception, just observe it)
        """
        correlation_id = getattr(request, "observability_correlation_id", "unknown")

        try:
            logger.debug(
                f"Processing exception for {request.method} {request.path}: {exception.__class__.__name__}, correlation_id={correlation_id}"
            )
            # Record exception in tracing
            if self.tracing_manager and hasattr(request, "observability_span"):
                self.tracing_manager.record_exception(
                    request.observability_span, exception
                )

            # Record exception metrics
            if self.metrics_collector:
                self.metrics_collector.increment_exception_counter(request, exception)

            # Log exception
            if self.structured_logger:
                self.structured_logger.log_exception(request, exception, correlation_id)

        except Exception as e:
            logger.error(
                "Error in ObservabilityMiddleware.process_exception",
                exc_info=True,
                extra={
                    "correlation_id": correlation_id,
                    "original_exception": str(exception),
                },
            )

        return None


class AsyncObservabilityMiddleware:
    """
    Async version of the observability middleware for async Django applications.

    This middleware provides the same functionality as ObservabilityMiddleware
    but is designed to work with Django's async views and middleware stack.
    """

    def __init__(self, get_response: Callable, config=None):
        """
        Initialize the async middleware.

        Args:
            get_response: The next middleware or view function in the chain
        """
        self.get_response = get_response
        self.config = get_config()

        # Check if observability is enabled
        if not self.config.is_enabled():
            logger.info("Django Observability is disabled")
            raise MiddlewareNotUsed("Django Observability is disabled")

        # Check if async support is enabled
        if not self.config.get("ASYNC_ENABLED", True):
            logger.info("Django Observability async support is disabled")
            raise MiddlewareNotUsed("Django Observability async support is disabled")

        # Initialize components
        self.tracing_manager = (
            TracingManager(self.config) if self.config.is_tracing_enabled() else None
        )
        self.metrics_collector = (
            get_metrics_collector(self.config)
            if self.config.is_metrics_enabled()
            else None
        )
        self.structured_logger = (
            StructuredLogger(self.config) if self.config.is_logging_enabled() else None
        )

        logger.info("Django Observability Async Middleware initialized")

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process request and response asynchronously.

        Args:
            request: The Django HttpRequest object

        Returns:
            The HttpResponse object
        """
        # Skip excluded paths
        if is_excluded_path(request.path, self.config.get("EXCLUDE_PATHS", [])):
            logger.debug(f"Skipping request due to excluded path: {request.path}")
            return await self.get_response(request)

        # Add correlation ID and start time
        correlation_id = str(uuid.uuid4())
        request.observability_correlation_id = correlation_id
        request.observability_start_time = time.time()

        span = None

        try:
            logger.debug(
                f"Processing request: {request.method} {request.path}, correlation_id={correlation_id}"
            )
            # Start tracing
            if self.tracing_manager:
                span = self.tracing_manager.start_request_span(request, correlation_id)
                request.observability_span = span

            # Log incoming request
            if self.structured_logger:
                self.structured_logger.log_request_start(request, correlation_id)

            # Increment request counter
            if self.metrics_collector:
                logger.debug(
                    f"Calling start_request for {request.method} {request.path}"
                )
                if not hasattr(self.metrics_collector, "_instrument_database"):
                    self.metrics_collector.start_request(request)
                else:
                    logger.debug("Skipping database instrumentation in async context")

            # Process the request
            response = await self.get_response(request)

            # Calculate duration
            duration = time.time() - request.observability_start_time

            logger.debug(
                f"Processing response: {request.method} {request.path}, status={response.status_code}, duration={duration}, correlation_id={correlation_id}"
            )

            # Record metrics
            if self.metrics_collector:
                self.metrics_collector.end_request(request, response, duration)

            # Log response
            if self.structured_logger:
                self.structured_logger.log_request_end(
                    request, response, duration, correlation_id
                )

            if self.config.get("ADD_CORRELATION_HEADER", False):
                response["X-Correlation-ID"] = correlation_id
            return response

        except Exception as exception:
            try:
                logger.debug(
                    f"Processing exception for {request.method} {request.path}: {exception.__class__.__name__}, correlation_id={correlation_id}"
                )
                if self.tracing_manager and span:
                    self.tracing_manager.record_exception(span, exception)

                if self.metrics_collector:
                    self.metrics_collector.increment_exception_counter(
                        request, exception
                    )

                if self.structured_logger:
                    self.structured_logger.log_exception(
                        request, exception, correlation_id
                    )

            except Exception as e:
                logger.error(
                    "Error recording exception in async middleware",
                    exc_info=True,
                    extra={"correlation_id": correlation_id},
                )

            raise exception

        finally:
            # End tracing
            if self.tracing_manager and span:
                duration = time.time() - request.observability_start_time
                response_obj = locals().get("response")
                self.tracing_manager.end_request_span(
                    span, request, response_obj, duration
                )
