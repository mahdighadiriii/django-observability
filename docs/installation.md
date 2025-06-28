# Installation

## Prerequisites
- Python 3.10+
- Django 3.2 to 5.x
- `prometheus-client>=0.17.0,<1.0.0`
- `opentelemetry-sdk==1.21.0`

## Installation Steps
1. Install the package via pip:
   ```bash
   pip install django-observability
   ```
2. Add `django_observability` to `INSTALLED_APPS` in `settings.py`:
   ```python
   INSTALLED_APPS = [
       ...,
       'django_observability',
   ]
   ```
3. Add the middleware to `MIDDLEWARE` in `settings.py`:
   ```python
   MIDDLEWARE = [
       ...,
       'django_observability.middleware.ObservabilityMiddleware',
   ]
   ```
4. (Optional) Install database-specific instrumentation:
   ```bash
   pip install django-observability[sqlite]
   # or
   pip install django-observability[mysql]
   # or
   pip install django-observability[memcached]
   ```
5. (Optional) Configure settings in `settings.py`:
   ```python
   DJANGO_OBSERVABILITY = {
       'METRICS_ENDPOINT': '/metrics/',
       'TRACING_ENABLED': True,
       'LOGGING_ENABLED': True,
       'SERVICE_NAME': 'my-django-app',
   }
   ```

## Verify Installation
Run the Django development server:
```bash
python manage.py runserver
```
Access `http://127.0.0.1:8000/metrics/` to confirm metrics are exposed.
