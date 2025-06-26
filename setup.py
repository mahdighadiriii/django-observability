from setuptools import setup, find_packages
from pathlib import Path

# Read the long description from README.md
long_description = Path("README.md").read_text(encoding="utf-8")

setup(
    name="django-observability",
    version="0.1.0",
    author="Mahdi Ghadiri",
    author_email="mahdighadiriafzal@gmail.com",
    description="A Django middleware for observability with OpenTelemetry, Prometheus, and structured logging",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mahdighadiriii/django-observability",  # Replace with actual URL
    project_urls={
        "Source": "https://github.com/mahdighadiriii/django-observability",
        "Bug Tracker": "https://github.com/mahdighadiriii/django-observability/issues",
        "Documentation": "https://github.com/mahdighadiriii/django-observability#readme",
    },
    packages=find_packages(exclude=["tests", "tests.*"]),
    include_package_data=True,
    install_requires=[
        "django>=3.2",
        "opentelemetry-api>=1.20.0",
        "opentelemetry-sdk>=1.20.0",
        "opentelemetry-instrumentation-django>=0.35b0",
        "opentelemetry-exporter-otlp-proto-grpc>=1.20.0",
        "prometheus-client>=0.17.0",
        "structlog>=23.1.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-django>=4.5.2",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.1",
            "flake8>=6.0.0",
            "black>=23.7.0",
            "isort>=5.12.0",
            "mypy>=1.5.1",
            "requests-mock>=1.11.0",
            "pre-commit>=3.3.3",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.0",
        "Framework :: Django :: 4.1",
        "Framework :: Django :: 4.2",
        "Framework :: Django :: 5.0",
        "Framework :: Django :: 5.1",
        "Framework :: Django :: 5.2",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Monitoring",
    ],
    python_requires=">=3.8",
    license="MIT",
)
