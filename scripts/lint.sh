#!/bin/bash
set -e

echo "Running Black for code formatting..."
black --check django_observability tests

echo "Running isort for import sorting..."
isort --check-only --diff django_observability tests

echo "Running Flake8 for linting..."
flake8 django_observability tests --max-line-length=88 --ignore=E203,W503,E501

echo "Running Ruff for additional linting..."
ruff check django_observability tests --fix

echo "Running mypy for type checking..."
mypy django_observability tests

echo "Linting complete."
