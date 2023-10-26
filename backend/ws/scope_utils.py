import asyncio
from typing import Any, Dict, Callable

from channels.db import database_sync_to_async
from django.http import HttpRequest

def ensure_async(method: Callable):
    if asyncio.iscoroutinefunction(method):
        return method
    return database_sync_to_async(method)

def request_from_scope(scope: Dict[str, Any]) -> HttpRequest:
    request = HttpRequest()
    request.path = scope.get("path")
    request.session = scope.get("session", None)

    request.META["HTTP_CONTENT_TYPE"] = "application/json"
    request.META["HTTP_ACCEPT"] = "application/json"

    for (header_name, value) in scope.get("headers", []):
        request.META[header_name.decode("utf-8")] = value.decode("utf-8")

    if scope.get("cookies"):
        request.COOKIES = scope.get("cookies")
    return request
