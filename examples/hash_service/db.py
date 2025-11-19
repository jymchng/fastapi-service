import sqlite3
from typing import Optional, Tuple, List
from fastapi_service import injectable, Scopes

@injectable(
    scope=Scopes.SINGLETON,
)
class SQLiteDB:
    def __init__(self, dsn: str = ":memory:"):
        self.dsn = dsn
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.dsn, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def init_schema(self) -> None:
        conn = self.connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS hashes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input TEXT NOT NULL UNIQUE,
                algorithm TEXT NOT NULL,
                digest TEXT NOT NULL
            );
            """
        )
        conn.commit()

    def insert_hash(self, input_text: str, algorithm: str, digest: str) -> int:
        try:
            cur = self.connect().execute(
                "INSERT INTO hashes (input, algorithm, digest) VALUES (?, ?, ?)",
                (input_text, algorithm, digest),
            )
            self.connect().commit()
            return cur.lastrowid
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Duplicate input: {input_text}") from e

    def get_hash(self, id_: int) -> Optional[Tuple[int, str, str, str]]:
        cur = self.connect().execute(
            "SELECT id, input, algorithm, digest FROM hashes WHERE id = ?",
            (id_,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return (row["id"], row["input"], row["algorithm"], row["digest"])

    def get_by_input(self, input_text: str) -> Optional[Tuple[int, str, str, str]]:
        cur = self.connect().execute(
            "SELECT id, input, algorithm, digest FROM hashes WHERE input = ?",
            (input_text,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return (row["id"], row["input"], row["algorithm"], row["digest"])

    def list_hashes(self) -> List[Tuple[int, str, str, str]]:
        cur = self.connect().execute(
            "SELECT id, input, algorithm, digest FROM hashes ORDER BY id DESC"
        )
        rows = cur.fetchall()
        return [
            (r["id"], r["input"], r["algorithm"], r["digest"]) for r in rows
        ]

    def update_hash(self, id_: int, algorithm: str, digest: str) -> bool:
        cur = self.connect().execute(
            "UPDATE hashes SET algorithm = ?, digest = ? WHERE id = ?",
            (algorithm, digest, id_),
        )
        self.connect().commit()
        return cur.rowcount > 0

    def delete_hash(self, id_: int) -> bool:
        cur = self.connect().execute("DELETE FROM hashes WHERE id = ?", (id_,))
        self.connect().commit()
        return cur.rowcount > 0