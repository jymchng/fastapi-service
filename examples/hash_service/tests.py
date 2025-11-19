import sys
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PARENT = Path(__file__).resolve().parents[2]
if str(PARENT / "src") not in sys.path:
    sys.path.insert(0, str(PARENT / "src"))


from examples.hash_service.app import app
client = TestClient(app)


def test_create_get_list_update_delete():
    r = client.post("/hash", params={"text": "hello", "algorithm": "sha256"})
    assert r.status_code == 200
    body = r.json()
    assert body["algorithm"] == "sha256"
    assert body["digest"]
    hid = body["id"]

    r = client.get(f"/hash/{hid}")
    assert r.status_code == 200
    item = r.json()
    assert item["id"] == hid

    r = client.get("/hash")
    assert r.status_code == 200
    lst = r.json()
    assert isinstance(lst, list)
    assert any(x["id"] == hid for x in lst)

    r = client.put(f"/hash/{hid}", params={"algorithm": "md5"})
    assert r.status_code == 200
    updated = r.json()
    assert updated["algorithm"] == "md5"

    r = client.delete(f"/hash/{hid}")
    assert r.status_code == 200
    assert r.json() == {"deleted": hid}

    r = client.get(f"/hash/{hid}")
    assert r.status_code == 404


def test_error_on_duplicate_and_unsupported_algorithm():
    r = client.post("/hash", params={"text": "hello", "algorithm": "sha256"})
    assert r.status_code == 200
    r = client.post("/hash", params={"text": "hello", "algorithm": "sha256"})
    assert r.status_code == 400
    assert "Duplicate" in r.json()["detail"]

    r = client.post("/hash", params={"text": "oops", "algorithm": "badalgo"})
    assert r.status_code == 400
    assert "Unsupported" in r.json()["detail"]