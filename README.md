# fastapi-service

[![version](https://img.shields.io/badge/version-0.1.0-blue.svg)](pyproject.toml)
[![Build](https://img.shields.io/badge/build-nox-success.svg)](noxfile.py)
[![Coverage](https://img.shields.io/badge/coverage-%E2%89%A590%25-brightgreen.svg)](pytest.ini)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](#license)

A lightweight dependency injection layer for FastAPI. It provides an `@injectable` decorator to mark classes for injection, a minimal `Container` to resolve dependencies, and seamless integration with FastAPI’s `Depends`. It supports singleton/transient scopes, auto-resolution from type hints, request-scoped resolution, and circular dependency detection.

## Table of Contents

- [Installation](#installation)
- [Quickstart](#quickstart)
- [Usage Guide](#usage-guide)
- [API Overview](#api-overview)
- [Configuration](#configuration)
- [Features](#features)
- [Troubleshooting](#troubleshooting)
- [Testing](#testing)
- [Development](#development)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [FAQ](#faq)
- [Contact](#contact)

## Installation

### Prerequisites

- Python 3.9+
- FastAPI
- Optional: Nox for automation; pytest/pytest-cov for testing

### Setup

```bash
# Clone
git clone <repo-url>
cd fastapi-service

# Install with uv (recommended) or pip
uv pip install -e .
# or
python -m pip install -e .

# Run tests
python -m pytest -q

# Using Nox (optional)
nox -s test
```

### Configuration

- `PYTHONPATH` should include `src` for a src-layout project.
- Environment variables:
  - `TEST_LOAD_FACTOR`: controls performance test load (default `25`).

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

### Common Commands

```bash
# Run unit/integration/security/performance tests
python -m pytest -q

# With coverage gate (90%):
python -m pytest --cov=src/fastapi_service --cov-report=term-missing

# Nox helpers
nox -s test
nox -s benchmark
```

## Usage Guide

Endpoint injection:

```python
from fastapi import FastAPI
from fastapi_service import injectable, Depends

@injectable
class GreetingService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}"

app = FastAPI()

@app.get("/greet/{name}")
def greet(name: str, svc: GreetingService = Depends(GreetingService)):
    return {"message": svc.greet(name)}
```

Singleton shared across routes:

```python
from fastapi_service import injectable, Depends, Scopes

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
```

Async dependencies:

```python
@injectable
class AsyncSvc:
    async def process(self):
        return "ok"

@app.get("/async")
async def route(svc: AsyncSvc = Depends(AsyncSvc)):
    return {"result": await svc.process()}
```

### Diagram

```
[Request] → FastAPI → Depends/Inject → Container.resolve → Instance
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

## Configuration

- `FASTAPI_REQUEST_KEY`: internal key used to pass `Request` into resolution.
- `TEST_LOAD_FACTOR`: performance tests load factor; default `25` (see `tests/conftest.py`).
- Nox sessions for automation: `test`, `benchmark`, `check`, `lint`, `build` (see `noxfile.py`).

## Troubleshooting

- Import errors in `injectable`: ensure module imports reference `fastapi_service.*`
- Undecorated classes must have type hints; otherwise resolution fails
- Use `Container.clear()` to reset singleton instances during testing
- Ensure `src` is on `PYTHONPATH` or added via `sys.path` in tests

## Testing

Run the suite:

```bash
python -m pytest
```

Coverage:

```bash
python -m pytest --cov=src/fastapi_service --cov-report=term-missing
```

Performance tests:

- Controlled by `TEST_LOAD_FACTOR` (default `25`). Increase locally to stress-test.

Integration tests:

- Use FastAPI’s `TestClient` to validate endpoint behaviors and DI.

Security tests:

- Validate input, auth, and data protection patterns.

Nox helpers:

```bash
nox -s test
nox -s benchmark
nox -s check
nox -s lint
nox -s build
```

## Development

### Contribution Guidelines

- Create feature branches and use conventional commits.
- Add unit/integration tests for new behavior; maintain coverage ≥ 90%.
- Follow existing code style; prefer type hints and explicit DI.

### Code of Conduct

- Be respectful and collaborative; report violations via project issues.

### Build/Deployment

```bash
nox -s build
```

Release helpers exist in `noxfile.py` (e.g., `release_check`, `version_sync`).

## License

MIT License. See `LICENSE` for details.

## Acknowledgments

- FastAPI for the dependency system and testing utilities.
- Starlette for the ASGI underpinnings.

## FAQ

- Why another DI layer?
  - Minimal, explicit DI aligned with FastAPI’s `Depends` while offering lifecycle scopes and auto-resolution.

- Do I need to decorate every class?
  - No. Undecorated classes/functions with type hints can be auto-resolved, but `@injectable` enables lifecycle and metadata capture.

- How do I inject `Request` or path/query params?
  - Use FastAPI parameters in constructor type hints and route wiring; request context is passed via `Depends`/`Inject`.

## Contact

- Maintainers: open issues and PRs on the repository.
- For security disclosures, contact the maintainers privately.