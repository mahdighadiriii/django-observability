"""
Configuration management for Django Observability.

This module handles all configuration aspects including Django settings integration,
environment variables, and validation with sensible defaults.
"""

import os
from typing import Any, Dict, List

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class ObservabilityConfig:
    """
    Centralized configuration for Django Observability middleware.

    This class handles configuration from multiple sources:
    1. Django settings (DJANGO_OBSERVABILITY)
    2. Environment variables
    3. Sensible defaults
    """

    def __init__(self):
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from Django settings and environment."""
        # Default configuration
        config = {
            # Tracing configuration
            "TRACING_ENABLED": True,
            "TRACING_SERVICE_NAME": self._get_service_name(),
            "TRACING_SAMPLE_RATE": 0.1,
            "TRACING_PROPAGATORS": ["tracecontext", "baggage"],
            "TRACING_EXPORT_ENDPOINT": None,
            "JAEGER_ENDPOINT": None,
            "ZIPKIN_ENDPOINT": None,
            # Metrics configuration
            "METRICS_ENABLED": True,
            "METRICS_PREFIX": "django_app",
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
            # Logging configuration
            "LOGGING_ENABLED": True,
            "LOGGING_FORMAT": "json",
            "LOGGING_LEVEL": "INFO",
            "LOGGING_INCLUDE_HEADERS": False,
            "LOGGING_INCLUDE_BODY": False,
            "LOGGING_SENSITIVE_HEADERS": ["authorization", "cookie", "x-api-key"],
            # General configuration
            "ENABLED": True,
            "DEBUG_MODE": False,
            "EXCLUDE_PATHS": ["/health/", "/metrics/", "/favicon.ico"],
            "ASYNC_ENABLED": True,
            "ADD_CORRELATION_HEADER": False,
            # Integration settings
            "INTEGRATE_DB_TRACING": True,
            "INTEGRATE_CACHE_TRACING": True,
            "INTEGRATE_TEMPLATE_TRACING": True,
            "INTEGRATE_REQUESTS_TRACING": True,
        }

        # Override with Django settings
        django_config = getattr(settings, "DJANGO_OBSERVABILITY", {})
        config.update(django_config)

        # Override with environment variables
        env_overrides = self._load_env_config()
        config.update(env_overrides)

        # Validate configuration
        self._validate_config(config)

        return config

    def _get_service_name(self) -> str:
        """Get service name from various sources."""
        # Try environment variable first
        service_name = os.getenv("OTEL_SERVICE_NAME")
        if service_name:
            return service_name

        # Try Django project name
        if hasattr(settings, "ROOT_URLCONF"):
            return settings.ROOT_URLCONF.split(".")[0]

        # Fallback
        return "django-app"

    def _load_env_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        env_mapping = {
            "DJANGO_OBSERVABILITY_ENABLED": ("ENABLED", bool),
            "DJANGO_OBSERVABILITY_DEBUG": ("DEBUG_MODE", bool),
            "DJANGO_OBSERVABILITY_TRACING_ENABLED": ("TRACING_ENABLED", bool),
            "DJANGO_OBSERVABILITY_METRICS_ENABLED": ("METRICS_ENABLED", bool),
            "DJANGO_OBSERVABILITY_LOGGING_ENABLED": ("LOGGING_ENABLED", bool),
            "DJANGO_OBSERVABILITY_SAMPLE_RATE": ("TRACING_SAMPLE_RATE", float),
            "DJANGO_OBSERVABILITY_METRICS_PREFIX": ("METRICS_PREFIX", str),
            "OTEL_EXPORTER_OTLP_ENDPOINT": ("TRACING_EXPORT_ENDPOINT", str),
            "JAEGER_ENDPOINT": ("JAEGER_ENDPOINT", str),
            "ZIPKIN_ENDPOINT": ("ZIPKIN_ENDPOINT", str),
        }

        config = {}
        for env_key, (config_key, type_func) in env_mapping.items():
            value = os.getenv(env_key)
            if value is not None:
                try:
                    if type_func == bool:
                        config[config_key] = value.lower() in ("true", "1", "yes", "on")
                    else:
                        config[config_key] = type_func(value)
                except (ValueError, TypeError) as e:
                    raise ImproperlyConfigured(
                        f"Invalid value for {env_key}: {value}. Error: {e}"
                    )

        return config

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration values."""
        # Validate sample rate
        sample_rate = config.get("TRACING_SAMPLE_RATE", 0.1)
        if not 0.0 <= sample_rate <= 1.0:
            raise ImproperlyConfigured(
                f"TRACING_SAMPLE_RATE must be between 0.0 and 1.0, got {sample_rate}"
            )

        # Validate logging format
        log_format = config.get("LOGGING_FORMAT", "json")
        if log_format not in ("json", "text"):
            raise ImproperlyConfigured(
                f"LOGGING_FORMAT must be 'json' or 'text', got {log_format}"
            )

        # Validate exclude paths
        exclude_paths = config.get("EXCLUDE_PATHS", [])
        if not isinstance(exclude_paths, list):
            raise ImproperlyConfigured("EXCLUDE_PATHS must be a list")

    def _ensure_initialized(self) -> None:
        """Ensure configuration is initialized (for testing compatibility)."""
        if not hasattr(self, "_config") or self._config is None:
            self._config = self._load_config()

    def force_reload(self) -> None:
        """Force reload configuration (for testing)."""
        self._config = self._load_config()

    def get(self, key: str, default=None):
        """Get configuration value."""
        return self._config.get(key, default)

    def is_enabled(self) -> bool:
        """Check if observability is enabled."""
        return self._config.get("ENABLED", True)

    def is_tracing_enabled(self) -> bool:
        """Check if tracing is enabled."""
        return self.is_enabled() and self._config.get("TRACING_ENABLED", True)

    def is_metrics_enabled(self) -> bool:
        """Check if metrics collection is enabled."""
        return self.is_enabled() and self._config.get("METRICS_ENABLED", True)

    def is_logging_enabled(self) -> bool:
        """Check if structured logging is enabled."""
        return self.is_enabled() and self._config.get("LOGGING_ENABLED", True)

    def should_trace_request(self, path: str) -> bool:
        """Determine if a request path should be traced."""
        if not self.is_enabled():
            return False

        exclude_paths = self._config.get("EXCLUDE_PATHS", [])
        return not any(path.startswith(excluded) for excluded in exclude_paths)

    def get_service_name(self) -> str:
        """Get the service name for tracing."""
        return self._config.get("TRACING_SERVICE_NAME", "django-app")

    def get_sample_rate(self) -> float:
        """Get the tracing sample rate."""
        sample_rate = self._config.get("TRACING_SAMPLE_RATE", 0.1)
        if not 0.0 <= sample_rate <= 1.0:
            raise ValueError(
                f"TRACING_SAMPLE_RATE must be between 0.0 and 1.0, got {sample_rate}"
            )
        return sample_rate

    def get_metrics_prefix(self) -> str:
        """Get the metrics prefix."""
        return self._config.get("METRICS_PREFIX", "django_app")

    def get_metrics_labels(self) -> Dict[str, str]:
        """Get default metrics labels."""
        return self._config.get("METRICS_LABELS", {})

    def get_sensitive_headers(self) -> List[str]:
        """Get list of sensitive headers to exclude from logging."""
        return self._config.get("LOGGING_SENSITIVE_HEADERS", [])

    def get_exclude_paths(self) -> List[str]:
        """Get list of paths to exclude from tracing."""
        return self._config.get("EXCLUDE_PATHS", [])

    def as_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary (useful for debugging)."""
        return self._config.copy()


# Global configuration instance
config = ObservabilityConfig()


def get_config() -> ObservabilityConfig:
    """Get the global configuration instance."""
    return config


def reload_config() -> ObservabilityConfig:
    """Reload configuration (useful for testing)."""
    global config
    config = ObservabilityConfig()
    return config
