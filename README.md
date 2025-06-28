# Django Observability

A production-ready Django middleware for comprehensive observability, integrating **OpenTelemetry** for distributed tracing, **Prometheus** for metrics, and **structured logging** with correlation ID tracking.

## Features
- **Distributed Tracing**: Track request flows across services using OpenTelemetry with support for Jaeger, Zipkin, or OTLP exporters.
- **Metrics Collection**: Expose Prometheus metrics for HTTP requests, response sizes, and active request counts.
- **Structured Logging**: Log requests, responses, and exceptions in JSON format with correlation IDs.
- **Async Support**: Compatible with synchronous and asynchronous Django views.
- **Configurable**: Customize via Django settings or environment variables.
- **Non-Intrusive**: Minimal performance overhead with graceful error handling.

## Installation
Install the package:
```bash
pip install django-observability
```

Add to `INSTALLED_APPS` in `settings.py`:
```python
INSTALLED_APPS = [
    ...,
    'django_observability',
]
```

Add the middleware to `MIDDLEWARE` in `settings.py`:
```python
MIDDLEWARE = [
    ...,
    'django_observability.middleware.ObservabilityMiddleware',
]
```

Configure in `settings.py` (optional):
```python
DJANGO_OBSERVABILITY = {
    'TRACING_ENABLED': True,
    'METRICS_ENABLED': True,
    'LOGGING_ENABLED': True,
    'SERVICE_NAME': 'my-django-app',
    'OTEL_EXPORTER': {
        'endpoint': 'http://localhost:4317',
        'protocol': 'grpc',
    },
}
```

Add the metrics endpoint in `urls.py`:
```python
from django.urls import path
from django_observability.metrics import metrics_view

urlpatterns = [
    path('metrics/', metrics_view, name='metrics'),
]
```

## Documentation
Detailed guides are available in the [docs/](docs/) folder:
- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Usage](docs/usage.md)
- [Contributing](docs/contributing.md)

## Examples
- `examples/basic_django_app/`: Minimal Django app showcasing observability setup.
- `examples/advanced_config/`: Advanced configuration with custom metrics and tracing.

## Requirements
- Python 3.10+
- Django 3.2 to 5.x
- See `requirements/base.txt` for full dependencies.

## Contributing
Contributions are welcome! See [CONTRIBUTING.md](docs/contributing.md) for details on setting up the development environment, code style, and submitting pull requests.

## License
MIT License. See [LICENSE](LICENSE) for details.
