from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_service import injectable, Depends


def test_injectable_with_custom_new_and_request_resolution():
    app = FastAPI()

    @injectable
    class B:
        def __init__(self):
            pass

    @injectable
    class NewSvc:
        def __new__(cls, b: B):
            inst = super().__new__(cls)
            return inst

        def __init__(self, b: B):
            self.b = b

    @app.get("/x")
    def route(s: NewSvc = Depends(NewSvc)):
        return {"ok": isinstance(s.b, B)}

    client = TestClient(app)
    assert client.get("/x").json() == {"ok": True}
