from fastapi import FastAPI, HTTPException, Depends
from fastapi.testclient import TestClient
from fastapi_service import injectable


def test_security_input_validation_with_exception():
    app = FastAPI()
    client = TestClient(app)

    @injectable
    class Validator:
        def validate(self, value: int) -> int:
            if value < 0:
                raise HTTPException(status_code=400, detail="Invalid value")
            return value

    @app.get("/validate/{value}")
    def route(value: int, v: Validator = Depends(Validator)):
        return {"validated": v.validate(value)}

    assert client.get("/validate/10").status_code == 200
    assert client.get("/validate/-1").status_code == 400


def test_security_authentication_authorization_headers():
    app = FastAPI()
    client = TestClient(app)

    from fastapi import Header

    @injectable
    class Auth:
        def verify(self, token: str) -> bool:
            return token == "valid"

    @app.get("/secure")
    def secure(authorization: str = Header(None), auth: Auth = Depends(Auth)):
        if not authorization or not auth.verify(authorization):
            return {"error": "Unauthorized"}
        return {"message": "Authorized"}

    assert client.get("/secure").json() == {"error": "Unauthorized"}
    assert client.get("/secure", headers={"authorization": "valid"}).json() == {
        "message": "Authorized"
    }


def test_security_data_protection_no_secret_leak():
    app = FastAPI()
    client = TestClient(app)

    @injectable
    class SecretSvc:
        def __init__(self):
            self.secret = "TOP_SECRET"

        def public(self):
            return "ok"

    @app.get("/info")
    def info(s: SecretSvc = Depends(SecretSvc)):
        return {"status": s.public()}

    body = client.get("/info").json()
    text = str(body)
    assert "TOP_SECRET" not in text