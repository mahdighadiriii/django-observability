# Configuration

## Default Settings
The `django-observability` package provides sensible defaults but is fully customizable.

## Configuration Options
Add to `settings.py`:

```python
DJANGO_OBSERVABILITY = {
    # Enable/disable features
    'TRACING_ENABLED': True,
    'METRICS_ENABLED': True,
    'LOGGING_ENABLED': True,
    
    # Metrics endpoint
    'METRICS_ENDPOINT': '/metrics/',
    
    # Service name for tracing
    'SERVICE_NAME': 'my-django-app',
    
    # OpenTelemetry exporter settings
    'OTEL_EXPORTER': {
        'endpoint': 'http://localhost:4317',
        'protocol': 'grpc',  # or 'http', 'jaeger', 'zipkin'
    },
    
    # Logging settings
    'LOGGING_FORMAT': 'json',
    'LOGGING_LEVEL': 'INFO',
    
    # Sensitive data filtering
    'SENSITIVE_FIELDS': ['password', 'token', 'secret'],
}
```

## Environment Variables
Override settings with environment variables:
```bash
export DJANGO_OBSERVABILITY__TRACING_ENABLED=True
export DJANGO_OBSERVABILITY__SERVICE_NAME=my-app
```

## Database Instrumentation
Enable database-specific tracing:
```python
INSTALLED_APPS = [
    ...,
    'opentelemetry.instrumentation.sqlite3',  # or .mysql, .redis
]
```

## Validation
Settings are validated on startup, raising clear exceptions for invalid configurations.
