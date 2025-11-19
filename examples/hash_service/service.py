import hashlib
from typing import Optional, Dict, Any
from fastapi_service import injectable, Scopes
from .db import SQLiteDB


@injectable(scope=Scopes.SINGLETON)
class HashService:
    def __init__(self):
        self.algorithms = {"sha256": hashlib.sha256, "md5": hashlib.md5}

    def compute(self, text: str, algorithm: str = "sha256") -> Dict[str, Any]:
        if algorithm not in self.algorithms:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        h = self.algorithms[algorithm]()
        h.update(text.encode("utf-8"))
        return {"algorithm": algorithm, "digest": h.hexdigest(), "input": text}


@injectable(scope=Scopes.SINGLETON)
class HashDBService:
    def __init__(self, db: SQLiteDB, svc: HashService):
        self.db = db
        self.svc = svc
        self.db.init_schema()

    def create(self, text: str, algorithm: str = "sha256") -> Dict[str, Any]:
        payload = self.svc.compute(text, algorithm)
        id_ = self.db.insert_hash(payload["input"], payload["algorithm"], payload["digest"])
        payload["id"] = id_
        return payload

    def get(self, id_: int) -> Optional[Dict[str, Any]]:
        row = self.db.get_hash(id_)
        if not row:
            return None
        return {"id": row[0], "input": row[1], "algorithm": row[2], "digest": row[3]}

    def get_by_input(self, input_text: str) -> Optional[Dict[str, Any]]:
        row = self.db.get_by_input(input_text)
        if not row:
            return None
        return {"id": row[0], "input": row[1], "algorithm": row[2], "digest": row[3]}

    def list(self) -> list[Dict[str, Any]]:
        rows = self.db.list_hashes()
        return [
            {"id": r[0], "input": r[1], "algorithm": r[2], "digest": r[3]} for r in rows
        ]

    def update(self, id_: int, algorithm: str) -> Optional[Dict[str, Any]]:
        item = self.get(id_)
        if not item:
            return None
        payload = self.svc.compute(item["input"], algorithm)
        ok = self.db.update_hash(id_, payload["algorithm"], payload["digest"])
        if not ok:
            return None
        payload["id"] = id_
        return payload

    def delete(self, id_: int) -> bool:
        return self.db.delete_hash(id_)