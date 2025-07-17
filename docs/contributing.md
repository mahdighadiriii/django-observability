# Contributing

## Getting Started
1. Clone the repository:
   ```bash
   git clone https://github.com/mahdighadiriii/django-observability.git
   ```
2. Install development dependencies:
   ```bash
   pip install -r requirements/dev.txt
   ```
3. Set up pre-commit hooks:
   ```bash
   pre-commit install
   ```
4. Run tests:
   ```bash
   ./scripts/test.sh
   ```

## Code Style
- Follow PEP 8.
- Use Black for formatting (`line-length=88`).
- Use isort for import sorting.
- Run Flake8 and Ruff for linting.
- Run mypy for type checking.

## Submitting Changes
1. Create a feature branch:
   ```bash
   git checkout -b feature/my-feature
   ```
2. Write tests for new features.
3. Run linters and tests:
   ```bash
   ./scripts/lint.sh
   ./scripts/test.sh
   ```
4. Submit a pull request to the `develop` branch.

## Issues
Report bugs or suggest features via GitHub Issues.

## Release Process
Maintainers handle releases using `./scripts/release.sh`.