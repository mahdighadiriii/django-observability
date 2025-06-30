class ObservabilityError(Exception):
    """Base exception for Django Observability errors."""

    pass


class ConfigurationError(ObservabilityError):
    """Raised when configuration is invalid."""

    pass
