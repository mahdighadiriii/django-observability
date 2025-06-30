class ObservabilityError(Exception):
    """Base exception for Django Observability errors."""


class ConfigurationError(ObservabilityError):
    """Raised when configuration is invalid."""
