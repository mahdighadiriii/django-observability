# Django Observability

A production-ready Django middleware for comprehensive observability, integrating OpenTelemetry for distributed tracing, Prometheus for metrics, and structured logging with correlation ID tracking.

## Features
- **Distributed Tracing**: Tracks request flow across services using OpenTelemetry.
- **Metrics Collection**: Exposes Prometheus metrics for HTTP requests, database queries, and cache operations.
- **Structured Logging**: Logs requests, responses, and exceptions in JSON or text format.
- **Async Support**: Compatible with both sync and async Django views.
- **Configurable**: Extensive configuration options via Django settings or environment variables.
- **Non-Intrusive**: Minimal overhead with graceful degradation on errors.

## Installation
```bash
pip install django-observability
```

Add to `MIDDLEWARE` in `settings.py`:
```python
MIDDLEWARE = [
    ...
    'django_observability.middleware.ObservabilityMiddleware',
]
```

Configure in `settings.py`:
```python
DJANGO_OBSERVABILITY = {
    'TRACING_ENABLED': True,
    'METRICS_ENABLED': True,
    'LOGGING_ENABLED': True,
    'TRACING_EXPORT_ENDPOINT': 'http://localhost:4317',
}
```

Add metrics endpoint in `urls.py`:
```python
from django.urls import path
from django_observability.metrics import metrics_view

urlpatterns = [
    path('metrics/', metrics_view, name='metrics'),
]
```

## Documentation
- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Usage](docs/usage.md)
- [Contributing](docs/contributing.md)

## Examples
- `examples/basic_django_app`: Minimal Django app with observability.
- `examples/advanced_config`: Advanced configuration with custom metrics and tracing.

## Contributing
Contributions are welcome! See [CONTRIBUTING.md](docs/contributing.md) for details.

## License
MIT License. See [LICENSE](LICENSE) for details.
