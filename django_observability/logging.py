"""
Structured Logging for Django Observability.

This module provides structured logging capabilities with JSON formatting,
correlation ID tracking, and integration with Django's logging system.
"""

import json
import logging
import time
from datetime import datetime, timezone

from django.http import HttpRequest, HttpResponse

from .config import ObservabilityConfig
from .utils import get_client_ip, get_view_name, sanitize_headers


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.

    This formatter converts log records to JSON format with consistent structure
    and includes observability-specific fields.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the JSON formatter."""
        super().__init__(*args, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: The log record to format

        Returns:
            JSON formatted log string
        """
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.process:
            log_entry["process_id"] = record.process
        if record.thread:
            log_entry["thread_id"] = record.thread

        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
            }:
                try:
                    json.dumps(value)
                    extra_fields[key] = value
                except (TypeError, ValueError):
                    extra_fields[key] = str(value)

        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry, ensure_ascii=False)


class StructuredLogger:
    """
    Structured logger for Django observability.

    This class provides methods for logging HTTP requests, responses, and exceptions
    with consistent structure and correlation ID tracking.
    """

    def __init__(self, config: ObservabilityConfig):
        """
        Initialize the structured logger.

        Args:
            config: The observability configuration instance
        """
        self.config = config
        self.logger = logging.getLogger("django_observability")
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Setup the logger with appropriate handlers and formatters."""
        # Set log level
        log_level = getattr(logging, self.config.get("LOGGING_LEVEL", "INFO").upper())
        self.logger.setLevel(log_level)

        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Create console handler
        handler = logging.StreamHandler()

        # Set formatter based on configuration
        log_format = self.config.get("LOGGING_FORMAT", "json")
        if log_format == "json":
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # Prevent propagation to avoid duplicate logs
        self.logger.propagate = False

    def _should_log_body(self, request: HttpRequest) -> bool:
        """
        Determine if the request body should be logged.

        Args:
            request: The Django HttpRequest object

        Returns:
            True if the body should be logged, False otherwise
        """
        content_type = request.META.get("CONTENT_TYPE", "").lower()
        return content_type.startswith(
            ("application/json", "text/", "multipart/form-data")
        )

    def log_request_start(self, request: HttpRequest, correlation_id: str) -> None:
        """
        Log the start of an HTTP request.

        Args:
            request: The Django HttpRequest object
            correlation_id: The correlation ID for this request
        """
        try:
            log_data = {
                "event": "request_start",
                "correlation_id": correlation_id,
                "http": {
                    "method": request.method,
                    "url": request.build_absolute_uri(),
                    "path": request.path,
                    "query_string": request.META.get("QUERY_STRING", ""),
                    "scheme": request.scheme,
                    "host": request.get_host(),
                    "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                    "view_name": get_view_name(request),
                },
                "network": {
                    "client_ip": get_client_ip(request),
                    "remote_addr": request.META.get("REMOTE_ADDR", ""),
                },
                "timing": {
                    "start_time": time.time(),
                },
            }

            # Add user information if available
            if hasattr(request, "user") and request.user.is_authenticated:
                log_data["user"] = {
                    "id": str(request.user.id),
                    "username": request.user.username,
                    "is_staff": request.user.is_staff,
                    "is_superuser": request.user.is_superuser,
                }

            # Add request headers if enabled
            if self.config.get("LOGGING_INCLUDE_HEADERS", False):
                headers = sanitize_headers(
                    request.META, self.config.get_sensitive_headers()
                )
                log_data["http"]["headers"] = headers

            # Add request body if enabled and safe
            if self.config.get("LOGGING_INCLUDE_BODY", False) and self._should_log_body(
                request
            ):
                try:
                    body = request.body.decode("utf-8")
                    log_data["http"]["body"] = body
                except (UnicodeDecodeError, AttributeError):
                    log_data["http"]["body"] = "[UNDECODABLE]"

            self.logger.info("Request started", extra=log_data)

        except Exception as e:
            self.logger.error(
                "Failed to log request start",
                exc_info=True,
                extra={"correlation_id": correlation_id},
            )

    def log_request_end(
        self,
        request: HttpRequest,
        response: HttpResponse,
        duration: float,
        correlation_id: str,
    ) -> None:
        """
        Log the completion of an HTTP request.

        Args:
            request: The Django HttpRequest object
            response: The Django HttpResponse object
            duration: The request duration in seconds
            correlation_id: The correlation ID for this request
        """
        try:
            log_data = {
                "event": "request_end",
                "correlation_id": correlation_id,
                "http": {
                    "method": request.method,
                    "url": request.build_absolute_uri(),
                    "path": request.path,
                    "status_code": response.status_code,
                    "view_name": get_view_name(request),
                },
                "timing": {
                    "duration_ms": duration * 1000,
                    "end_time": time.time(),
                },
            }

            # Add response headers if enabled
            if self.config.get("LOGGING_INCLUDE_HEADERS", False):
                headers = sanitize_headers(
                    {k: v for k, v in response.items()},
                    self.config.get_sensitive_headers(),
                )
                log_data["http"]["response_headers"] = headers

            # Add response body if enabled and safe
            if self.config.get("LOGGING_INCLUDE_BODY", False):
                content_type = response.get("Content-Type", "").lower()
                if content_type.startswith(("application/json", "text/")):
                    try:
                        log_data["http"]["response_body"] = response.content.decode(
                            "utf-8"
                        )
                    except UnicodeDecodeError:
                        log_data["http"]["response_body"] = "[UNDECODABLE]"

            self.logger.info("Request completed", extra=log_data)

        except Exception as e:
            self.logger.error(
                "Failed to log request end",
                exc_info=True,
                extra={"correlation_id": correlation_id},
            )

    def log_exception(
        self, request: HttpRequest, exception: Exception, correlation_id: str
    ) -> None:
        """
        Log an exception that occurred during request processing.

        Args:
            request: The Django HttpRequest object
            exception: The exception that occurred
            correlation_id: The correlation ID for this request
        """
        try:
            log_data = {
                "event": "exception",
                "correlation_id": correlation_id,
                "http": {
                    "method": request.method,
                    "url": request.build_absolute_uri(),
                    "path": request.path,
                    "view_name": get_view_name(request),
                },
                "exception": {
                    "type": exception.__class__.__name__,
                    "message": str(exception),
                },
            }

            self.logger.error("Request exception", exc_info=exception, extra=log_data)

        except Exception as e:
            self.logger.error(
                "Failed to log exception",
                exc_info=True,
                extra={"correlation_id": correlation_id},
            )
