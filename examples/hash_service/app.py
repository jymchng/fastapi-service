from fastapi import FastAPI, HTTPException
from fastapi_service import Depends, injectable, Scopes
from .service import HashDBService
from .db import SQLiteDB


@injectable(scope=Scopes.SINGLETON)
class DB(SQLiteDB):
    def __init__(self):
        super().__init__(":memory:")


app = FastAPI()


@app.post("/hash")
def create_hash(text: str, algorithm: str = "sha256", svc: HashDBService = Depends(HashDBService)):
    try:
        return svc.create(text, algorithm)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/hash/{id}")
def get_hash(id: int, svc: HashDBService = Depends(HashDBService)):
    item = svc.get(id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item


@app.get("/hash")
def list_hashes(svc: HashDBService = Depends(HashDBService)):
    return svc.list()


@app.put("/hash/{id}")
def update_hash(id: int, algorithm: str, svc: HashDBService = Depends(HashDBService)):
    item = svc.update(id, algorithm)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item


@app.delete("/hash/{id}")
def delete_hash(id: int, svc: HashDBService = Depends(HashDBService)):
    ok = svc.delete(id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": id}