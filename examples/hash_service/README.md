# Hash Service Example (FastAPI + SQLite + fastapi-service)

This example demonstrates how to use `@injectable` and dependency injection from `fastapi-service` to build a simple hash service backed by SQLite and exposed via FastAPI.

## Architecture

- `db.py`: SQLite database wrapper with schema initialization and CRUD operations.
- `service.py`: Business logic (`HashService` compute + `HashDBService` CRUD orchestrating DB and compute).
- `app.py`: FastAPI routes injecting `HashDBService` via `Depends`.
- `tests.py`: Unit tests using `TestClient` for API verification.

Flow:

```
Request → FastAPI → Depends(HashDBService) → HashDBService(db, compute) → SQLite
```

## Setup & Run

```bash
python -m pytest examples/hash-service/tests.py -q
```

## API Contracts

- `POST /hash?text=<str>&algorithm=<sha256|md5>` → `{id, input, algorithm, digest}`
- `GET /hash/{id}` → item or 404
- `GET /hash` → list of items
- `PUT /hash/{id}?algorithm=<sha256|md5>` → updated item or 404
- `DELETE /hash/{id}` → `{deleted: id}` or 404

## Notes

- `DB` is defined as an injectable subclass of `SQLiteDB` so it can be shared and schema-initialized once (singleton).
- Error cases are surfaced as HTTP 400/404 with descriptive messages.