import asyncio
from typing import Callable

from django.http import HttpRequest, HttpResponse


async def async_wrapper(get_response: Callable, request: HttpRequest) -> HttpResponse:
    """
    Wrapper to handle async middleware calls.

    Args:
        get_response: The next middleware or view function
        request: The Django HttpRequest object

    Returns:
        The HttpResponse object
    """
    if asyncio.iscoroutinefunction(get_response):
        return await get_response(request)
    return get_response(request)
