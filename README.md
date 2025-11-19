# fastapi-service

A lightweight dependency injection layer designed for FastAPI. It provides a decorator-based way to mark classes as injectable, a minimal container to resolve dependencies, and close integration with FastAPI’s `Depends` while supporting singleton and transient scopes, auto-resolution from type hints, request-scoped resolution, and circular dependency detection.

## Installation

Use the project in a `src` layout. Ensure your test or runtime environment includes the `src` directory in `PYTHONPATH` or add it to `sys.path` in tests.

## Quickstart

```python
from fastapi import FastAPI
from fastapi_service.injectable import injectable, Depends
from fastapi_service.enums import Scopes

@injectable(scope=Scopes.SINGLETON)
class Database:
    def __init__(self):
        self.url = "sqlite://"

@injectable
class Users:
    def __init__(self, db: Database):
        self.db = db
    def all(self):
        return ["alice", "bob"]

app = FastAPI()

@app.get("/users")
def list_users(svc: Users = Depends(Users)):
    return svc.all()
```

## Features

- Scopes with `Scopes.SINGLETON` and `Scopes.TRANSIENT`
- `@injectable` decorator attaches metadata and auto-discovers dependencies from type hints
- `Container.resolve` auto-resolves classes and functions using type hints
- Request-scoped resolution by passing the FastAPI `Request` through `Inject`/`Depends`
- Integration with regular FastAPI `Depends` and an `Inject` convenience wrapper
- Circular dependency detection
- Errors for missing type hints without defaults, and non-class dependency types

## API Overview

- `injectable(scope: Scopes = Scopes.TRANSIENT)`: Decorate a class as injectable, capturing its constructor type hints and scope.
- `Container.resolve(dependency, additional_context: dict = {})`: Resolve a dependency. Supports singleton caching, transient instantiation, auto-resolution for undecorated classes/functions, and FastAPI request context.
- `Container.clear()`: Clear registry/cache; useful for tests.
- `Inject(dependency, use_cache=True, container=None)`: Convenience wrapper producing a FastAPI `Depends` object that wires request context for DI.
- `Depends(dependency, use_cache=True, container=None)`: Alias of `Inject`.
- `helpers.get_body_field_should_embed_from_request(dependant, path_format)`: Inspect an endpoint and determine body embedding behavior.
- `helpers.get_body_from_request(request, body_field=None)`: Parse request body as JSON or bytes, raising `RequestValidationError` for invalid JSON.
- `helpers.get_solved_dependencies(request, endpoint, dependency_cache)`: Solve FastAPI dependencies for a given callable in the context of a request.
- `protocols.InjectableProtocol`: Runtime-checkable protocol used internally to detect injectable classes.

## Patterns

- Service layer composition via constructor injection
- Repository/service split with singleton repositories
- Request-scoped dependencies using `Request` and FastAPI parameter types (`Path`, `Query`, etc.)
- Avoid singleton depending on transient; this raises `ValueError` to protect lifecycle correctness

## Troubleshooting

- Import errors in `injectable`: ensure module imports reference `fastapi_service.*`
- Undecorated classes must have type hints; otherwise resolution fails
- Use `Container.clear()` to reset singleton instances during testing
- Ensure `src` is on `PYTHONPATH` or added via `sys.path` in tests

## Testing

Run the suite:
