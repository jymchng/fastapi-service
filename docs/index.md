# FastAPI Service

Effortless Dependency Injection for FastAPI applications.

## Features

- **Zero Configuration**: No XML, YAML, or complex setup required
- **Pythonic**: Uses standard type hints and decorators
- **FastAPI Native**: Works seamlessly with FastAPI's `Depends()` system
- **Automatic Resolution**: Dependencies are resolved automatically when needed
- **Scope Management**: Built-in singleton and transient scopes with safety checks
- **Test-Friendly**: Easy dependency mocking and test isolation

## Quick Start

```python
from fastapi import FastAPI, Depends
from fastapi_service import injectable

@injectable
class DatabaseService:
    def get_connection(self):
        return "Database Connection"

@injectable
class UserService:
    def __init__(self, db: DatabaseService):
        self.db = db
    
    def get_user(self, user_id: int):
        return {"id": user_id, "data": self.db.get_connection()}

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, service: UserService = Depends(UserService)):
    return service.get_user(user_id)
```

## Installation

```bash
pip install fastapi-service
```

## Why FastAPI Service?

Traditional dependency injection in FastAPI requires verbose boilerplate:

```python
# Without fastapi-service (manual wiring)
def get_db_service():
    return DatabaseService()

def get_user_service(db: DatabaseService = Depends(get_db_service)):
    return UserService(db)

@app.get("/users/{user_id}")
async def get_user(
    user_id: int, 
    service: UserService = Depends(get_user_service)
):
    return service.get_user(user_id)
```

With FastAPI Service, this becomes:

```python
# With fastapi-service (automatic wiring)
@app.get("/users/{user_id}")
async def get_user(
    user_id: int, 
    service: UserService = Depends(UserService)
):
    return service.get_user(user_id)
```

**60% less boilerplate code**, cleaner abstractions, and easier maintenance.

## Next Steps

- [Installation Guide](getting-started/installation.md) - Get up and running
- [Quick Start](getting-started/quick-start.md) - Build your first app
- [Tutorial](getting-started/tutorial.md) - Comprehensive walkthrough
- [Core Concepts](concepts/dependency-injection.md) - Learn the fundamentals