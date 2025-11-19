import asyncio
import pytest
from fastapi import Body
from starlette.requests import Request

from fastapi_service.helpers import get_solved_dependencies


def test_helpers_json_decode_error_on_invalid_body():
    async def receive():
        return {"type": "http.request", "body": b"{invalid json}", "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
    }
    request = Request(scope, receive)

    def endpoint(payload: dict = Body(...)):
        return payload

    with pytest.raises(Exception):
        asyncio.run(get_solved_dependencies(request, endpoint, {}))


def test_helpers_json_body_success_parsing():
    async def receive():
        return {"type": "http.request", "body": b'{\n "a": 1\n}', "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "headers": [],
        "query_string": b"",
    }
    request = Request(scope, receive)

    def endpoint(payload: dict = Body(...)):
        return payload

    # FastAPI requires inner astack in Request scope to solve dependencies
    import contextlib

    request.scope["fastapi_inner_astack"] = contextlib.AsyncExitStack()
    request.scope["fastapi_function_astack"] = contextlib.AsyncExitStack()
    solved = asyncio.run(get_solved_dependencies(request, endpoint, {}))
    assert "payload" in solved.values


def test_helpers_raw_bytes_body_when_non_json_content_type():
    async def receive():
        return {"type": "http.request", "body": b"raw-bytes", "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "headers": [(b"content-type", b"text/plain")],
        "query_string": b"",
    }
    request = Request(scope, receive)

    def endpoint(payload: bytes = Body(...)):
        return payload

    import contextlib

    request.scope["fastapi_inner_astack"] = contextlib.AsyncExitStack()
    request.scope["fastapi_function_astack"] = contextlib.AsyncExitStack()
    solved = asyncio.run(get_solved_dependencies(request, endpoint, {}))
    assert "payload" in solved.values
