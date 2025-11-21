import pytest
from fastapi.testclient import TestClient
from fastapi_service import injectable, Scopes
from fastapi import Depends, Request, Path


def test_fastapi_endpoints_basic_injection(app, client):
    @injectable
    class GreetingService:
        def greet(self, name: str) -> str:
            return f"Hello, {name}"

    @app.get("/greet/{name}")
    def greet(name: str, svc=Depends(GreetingService)):
        return {"message": svc.greet(name)}

    assert client.get("/greet/Alice").json() == {"message": "Hello, Alice"}


def test_fastapi_nested_dependencies(app, client):
    @injectable
    class Db:
        def query(self):
            return "data"

    @injectable
    class Cache:
        def __init__(self, db: Db):
            self.db = db

        def get(self):
            return f"cached:{self.db.query()}"

    @app.get("/data")
    def data(cache: Cache = Depends(Cache)):
        return {"data": cache.get()}

    assert client.get("/data").json() == {"data": "cached:data"}


def test_fastapi_async_route_with_dependency(app):
    client = TestClient(app)

    @injectable
    class AsyncSvc:
        async def process(self):
            return "ok"

    @app.get("/async")
    async def route(svc=Depends(AsyncSvc)):
        return {"result": await svc.process()}

    assert client.get("/async").json() == {"result": "ok"}


def test_fastapi_header_auth(app, client):
    from fastapi import Header

    @injectable
    class Auth:
        def verify(self, token: str) -> bool:
            return token == "valid"

    @app.get("/protected")
    def protected(authorization=Header(...), auth=Depends(Auth)):
        if not auth.verify(authorization):
            return {"error": "Unauthorized"}
        return {"message": "Authorized"}

    assert client.get("/protected", headers={"authorization": "valid"}).json() == {
        "message": "Authorized"
    }


def test_fastapi_singleton_shared_across_routes(app, client):
    @injectable(scope=Scopes.SINGLETON)
    class Counter:
        def __init__(self):
            self.count = 0

        def inc(self):
            self.count += 1
            return self.count

    @app.get("/c1")
    def c1(svc=Depends(Counter)):
        return {"count": svc.inc()}

    @app.get("/c2")
    def c2(svc=Depends(Counter)):
        return {"count": svc.inc()}

    assert client.get("/c1").json() == {"count": 1}
    assert client.get("/c2").json() == {"count": 2}


def test_transient_injectables_can_depend_on_singleton_injectables(app, client):
    @injectable(scope=Scopes.SINGLETON)
    class Db:
        def query(self):
            return "data"

    @injectable(scope=Scopes.TRANSIENT)
    class Cache:
        def __init__(self, db: Db):
            self.db = db

        def get(self):
            return f"cached:{self.db.query()}"

    @app.get("/data")
    def data(cache=Depends(Cache)):
        return {"data": cache.get()}

    assert client.get("/data").json() == {"data": "cached:data"}


def test_fastapi_cannot_resolve_any_random_depends(app, client):
    test_name: str = "James"

    def depends_on_path_two(name: str):
        assert name == test_name
        return name

    def depends_on_path(name=Depends(depends_on_path_two)):
        assert name == test_name
        return name

    @app.get("/{name}")
    def route(name: str = Depends(depends_on_path)):
        return {"name": name}

    assert client.get("/" + test_name).json() == {"name": test_name}
    assert client.get("/" + test_name).json() == {"name": test_name}


def test_singleton_injectable_cannot_depend_on_request_scoped_injectables(app, client):
    test_name: str = "James"

    def depends_on_path(name: str = Path()):
        assert name == test_name

    @injectable
    class RequestSvc:
        def __init__(self, req: Request, name = Depends(depends_on_path)):
            self.count = 0
            self.req = req
            self.name = name
            assert name == test_name

        def inc(self):
            self.count += 1
            return self.count

    @injectable(scope=Scopes.SINGLETON)
    class SingletonSvc:
        def __init__(self, req_svc: RequestSvc):
            self.req_svc = req_svc

        def get(self):
            return self.req_svc.inc()

    @app.get("/{name}")
    def route(svc=Depends(SingletonSvc)):
        return {"count": svc.get()}

    assert client.get("/" + test_name).json() == {"count": 1}
    assert client.get("/" + test_name).json() == {"count": 2}
