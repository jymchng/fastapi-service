from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_service import injectable, Depends, Scopes


def test_fastapi_endpoints_basic_injection(app, client):
    @injectable
    class GreetingService:
        def greet(self, name: str) -> str:
            return f"Hello, {name}"

    @app.get("/greet/{name}")
    def greet(name: str, svc: GreetingService = Depends(GreetingService)):
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
    async def route(svc: AsyncSvc = Depends(AsyncSvc)):
        return {"result": await svc.process()}

    assert client.get("/async").json() == {"result": "ok"}


def test_fastapi_header_auth(app, client):
    from fastapi import Header

    @injectable
    class Auth:
        def verify(self, token: str) -> bool:
            return token == "valid"

    @app.get("/protected")
    def protected(authorization: str = Header(...), auth: Auth = Depends(Auth)):
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
    def c1(svc: Counter = Depends(Counter)):
        return {"count": svc.inc()}

    @app.get("/c2")
    def c2(svc: Counter = Depends(Counter)):
        return {"count": svc.inc()}

    assert client.get("/c1").json() == {"count": 1}
    assert client.get("/c2").json() == {"count": 2}