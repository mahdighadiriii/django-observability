#!/bin/bash

# scripts/test.sh
set -euo pipefail

echo "Running tests with pytest..."

# Set Django settings module
export DJANGO_SETTINGS_MODULE="drfp.example_project.settings"

# Add project subdir to PYTHONPATH so Django can find the settings
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/drfp"


# Activate virtualenv if needed
# source .venv/bin/activate

# Run tests
python -m pytest \
    --cov=django_observability \
    --cov-report=html \
    --cov-report=term-missing \
    --cov-fail-under=80 \
    -v \
    tests/

echo "Tests completed successfully!"
