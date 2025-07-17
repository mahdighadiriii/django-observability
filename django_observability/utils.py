import logging
from typing import Dict, List

from django.http import HttpRequest
from django.urls import resolve

logger = logging.getLogger("django_observability.utils")


def get_client_ip(request: HttpRequest) -> str:
    """
    Get the client IP address from the request.

    Handles cases where the request is behind a proxy.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def sanitize_headers(
    headers: Dict[str, str], sensitive_headers: List[str]
) -> Dict[str, str]:
    """
    Sanitize HTTP headers by redacting sensitive information.

    Args:
        headers: Dictionary of HTTP headers
        sensitive_headers: List of header names to redact

    Returns:
        Sanitized headers dictionary
    """
    sanitized = {}
    sensitive_headers = [h.lower() for h in sensitive_headers]

    for key, value in headers.items():
        header_key = key.lower().replace("http_", "").replace("_", "-")
        if header_key in sensitive_headers:
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = value
    return sanitized


def is_excluded_path(path: str, exclude_paths: List[str]) -> bool:
    """
    Check if a path should be excluded from observability.

    Args:
        path: The request path
        exclude_paths: List of paths to exclude

    Returns:
        True if the path is excluded, False otherwise
    """
    return any(path.startswith(excluded) for excluded in exclude_paths)


def get_view_name(request: HttpRequest) -> str:
    """
    Get the view name for a request.

    Args:
        request: The Django HttpRequest object

    Returns:
        The view name or 'unknown' if not resolved
    """
    try:
        # Ensure resolver_match is populated
        if not hasattr(request, "resolver_match") or not request.resolver_match:
            resolver_match = resolve(request.path)
            request.resolver_match = resolver_match
            logger.debug(
                f"Manually resolved path {request.path}: {resolver_match.__dict__}"
            )
        view_name = request.resolver_match.view_name or "unknown"
        logger.debug(f"Resolved view_name for {request.path}: {view_name}")
        return view_name
    except Exception as e:
        logger.debug(f"Failed to resolve view name for {request.path}: {str(e)}")
        return "unknown"
