# Usage

## Basic Usage
After installation, the middleware tracks:
- HTTP request/response metrics (duration, count, response size)
- Structured JSON logs with correlation IDs
- OpenTelemetry spans for requests

Access metrics at `http://127.0.0.1:8000/metrics/`.

## Custom Metrics
Add custom metrics in views:
```python
from django_observability.metrics import django_app_custom_counter

def my_view(request):
    django_app_custom_counter.labels(
        endpoint='my_view',
        method=request.method,
        category='business'
    ).inc()
    return HttpResponse('Custom metric recorded')
```

## Tracing
Spans are created for each request. Add custom spans:
```python
from opentelemetry import trace

def my_view(request):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span('custom_operation'):
        # Your code here
        pass
    return HttpResponse('Traced operation')
```

## Logging
Logs include request details and correlation IDs. Add custom logs:
```python
import logging
logger = logging.getLogger('django_observability')

def my_view(request):
    logger.info('Custom event', extra={'event': 'custom_action', 'user_id': 123})
    return HttpResponse('Logged event')
```

## Monitoring
Use Prometheus for metrics and Grafana for visualization. Export traces to Jaeger, Zipkin, or an OTLP-compatible backend.
