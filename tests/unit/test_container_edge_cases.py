import pytest
from fastapi import FastAPI, Request, Path
from fastapi.testclient import TestClient
from fastapi_service.constants import FASTAPI_REQUEST_KEY
from fastapi_service.oracle import FastAPIOracle


def test_container_unregistered_dependency_error(container):
    class Unregistered:
        def __init__(self, missing: int):
            self.missing = missing

    assert container.resolve(Unregistered).missing == 0


def test_container_object_init_branch(container):
    class Empty:
        pass

    instance = container.resolve(Empty)
    assert isinstance(instance, Empty)


def test_container_missing_type_hint_raises(container):
    class Bad:
        def __init__(self, missing):
            self.missing = missing

    with pytest.raises(ValueError) as exc:
        container.resolve(Bad)
    assert (
        "Cannot resolve dependency for parameter 'missing' in Bad.__init__: type hint is missing."
        in str(exc.value)
    )


def test_container_non_callable_raises(container):
    with pytest.raises(ValueError) as exc:
        container.resolve(42)  # type: ignore[arg-type]
    assert "Cannot auto-resolve non-class type: 42" in str(exc.value)


def test_container_function_missing_type_raises(container):
    def f(unknown):
        return 1

    with pytest.raises(ValueError) as exc:
        container.resolve(f)
    assert (
        "Cannot resolve dependency for parameter 'unknown' in f: type hint is missing."
        in str(exc.value)
    )


def test_container_function_default_value_skips(container):
    def f(a: int = 1):
        return a

    class FakeOracle:
        def get_context(self, dependency):
            return {"a": 0}

    result = container.resolve(f, oracle=FakeOracle())
    assert result == 0


def test_container_auto_resolve_with_fastapi_request_values(container):
    app = FastAPI()
    client = TestClient(app)

    class RequestPlain:
        def __init__(self, req: Request, name: str = Path(...)):
            self.name = name
            self.client = req.client

    @app.get("/user/{name}")
    def route(request: Request, name: str):
        inst = container.resolve(RequestPlain, oracle=FastAPIOracle(request))
        return {"name": inst.name, "client": bool(inst.client)}

    body = client.get("/user/Alice").json()
    assert body == {"name": "Alice", "client": True}
