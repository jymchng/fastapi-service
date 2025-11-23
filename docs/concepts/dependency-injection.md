
# Dependency Injection

Dependency Injection (DI) is a core software design pattern that **inverts** the traditional control flow. Instead of a class creating its own dependencies, dependencies are **provided** (injected) from the outside. This fundamental principle is what makes `fastapi-service` so powerful yet simple.

## Why Dependency Injection Matters

### The Traditional Approach (Without DI)

Consider this typical pattern:

```python
class UserService:
    def __init__(self):
        # Hard-coding dependencies
        self.db = DatabaseConnection()
        self.cache = RedisCache()
        self.logger = FileLogger()

    def get_user(self, user_id: int):
        self.logger.log(f"Fetching user {user_id}")
        if cached := self.cache.get(f"user:{user_id}"):
            return cached
        user = self.db.query("SELECT * FROM users WHERE id = ?", user_id)
        self.cache.set(f"user:{user_id}", user)
        return user
```

**Problems with this approach:**

- ❌ **Tight Coupling**: `UserService` is directly tied to specific implementations
- ❌ **Difficult Testing**: Can't easily mock `DatabaseConnection` or `RedisCache`
- ❌ **Inflexible**: Changing the logger requires modifying the class
- ❌ **Hidden Dependencies**: It's not obvious what `UserService` needs to work

### The Dependency Injection Approach

```python
# With fastapi-service
from fastapi_service import injectable

@injectable
class UserService:
    def __init__(self, db: DatabaseService, cache: CacheService, logger: LoggerService):
        self.db = db
        self.cache = cache
        self.logger = logger

    def get_user(self, user_id: int):
        self.logger.log(f"Fetching user {user_id}")
        if cached := self.cache.get(f"user:{user_id}"):
            return cached
        user = self.db.get_user(user_id)
        self.cache.set(f"user:{user_id}", user)
        return user
```

**Benefits:**

- ✅ **Loose Coupling**: Depends on abstractions, not concrete implementations
- ✅ **Easy Testing**: Simply pass mock objects in tests
- ✅ **Flexible**: Swap implementations without changing the service
- ✅ **Explicit Dependencies**: Constructor clearly declares requirements

## How fastapi-service Implements DI

`fastapi-service` bridges the gap between **enterprise DI containers** and **FastAPI's native `Depends`** system without adding complexity.

### Key Principles

1. **Zero Configuration**: No XML, YAML, or complex setup
2. **Pythonic**: Uses standard type hints and decorators
3. **FastAPI Native**: Works seamlessly with `Depends()`
4. **Runtime Resolution**: Dependencies are resolved automatically when needed

### The Injection Lifecycle

```mermaid
graph TD
    A[FastAPI Endpoint] -->|Depends(UserService)| B[Dependency Resolver]
    B -->|Analyzes __init__| C[Type Hints Inspection]
    C -->|Finds dependencies| D[DatabaseService, CacheService, LoggerService]
    D -->|Recursively resolve| E[Create Instances]
    E -->|Inject into UserService| F[Return Service Instance]
    F -->|Use in endpoint| G[Handle Request]
```

**Step-by-step:**

1. **Declaration**: You annotate a class with `@injectable` and declare dependencies in `__init__` using type hints
2. **Registration**: The library registers the service and its dependency graph
3. **Resolution**: When the service is requested (via `Depends()`), the library:
   - Inspects the constructor's type hints
   - Creates instances of each dependency (recursively if needed)
   - Validates scopes to prevent lifecycle issues
   - Injects the dependencies into the service
   - Returns the fully-constructed service

### Example: Complete Workflow

```python
# services.py
from fastapi_service import injectable, Scopes

@injectable(scope=Scopes.SINGLETON)
class ConfigService:
    def get_config(self):
        return {"api_url": "https://api.example.com"}

@injectable
class DatabaseService:
    def __init__(self, config: ConfigService):
        self.connection_string = config.get_config()["api_url"]
    
    def query(self, sql: str):
        return f"Executing: {sql}"

@injectable
class UserService:
    def __init__(self, db: DatabaseService):
        self.db = db
    
    def get_user(self, user_id: int):
        return self.db.query(f"SELECT * FROM users WHERE id = {user_id}")

# main.py
from fastapi import FastAPI, Depends
from services import UserService

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, service: UserService = Depends(UserService)):
    # FastAPI automatically resolves the entire chain:
    # UserService → DatabaseService → ConfigService
    return {"user": service.get_user(user_id), "id": user_id}
```

When a request hits `/users/123`, this happens:

1. FastAPI sees `Depends(UserService)`
2. `fastapi-service` generates a factory function that knows how to build `UserService`
3. It sees `UserService` needs a `DatabaseService`
4. It sees `DatabaseService` needs a `ConfigService`
5. It creates `ConfigService` (SINGLETON scope, so reused across requests)
6. It creates `DatabaseService` with the config injected
7. It creates `UserService` with the database injected
8. The fully-built `UserService` is passed to your endpoint

## Comparison: Manual vs. Automatic DI

### Manual DI (Verbose Boilerplate)

```python
# Without fastapi-service - you write this manually
def get_config_service():
    return ConfigService()

def get_database_service(config: ConfigService = Depends(get_config_service)):
    return DatabaseService(config)

def get_user_service(db: DatabaseService = Depends(get_database_service)):
    return UserService(db)

@app.get("/users/{user_id}")
async def get_user(
    user_id: int, 
    service: UserService = Depends(get_user_service)
):
    return service.get_user(user_id)
```

### Automatic DI (With fastapi-service)

```python
# With fastapi-service - the library does this for you
@app.get("/users/{user_id}")
async def get_user(
    user_id: int, 
    service: UserService = Depends(UserService)  # Just reference the class!
):
    return service.get_user(user_id)
```

**Result**: 60% less boilerplate code, cleaner abstractions, and easier maintenance.

## Best Practices

### 1. Depend on Abstractions, Not Concretions

```python
# Good: Depend on a protocol or abstract base class
from typing import Protocol

class Logger(Protocol):
    def log(self, message: str): ...

@injectable
class FileLogger:
    def log(self, message: str):
        with open("app.log", "a") as f:
            f.write(message + "\n")

@injectable
class UserService:
    def __init__(self, logger: Logger):  # Depends on protocol
        self.logger = logger

# Easy to swap to a different logger without changing UserService
```

### 2. Use Constructor Injection (Not Setter Injection)

```python
# Preferred: Constructor injection
@injectable
class GoodService:
    def __init__(self, dependency: SomeDependency):
        self.dependency = dependency

# Avoid: Setter injection (more error-prone)
@injectable
class BadService:
    def set_dependency(self, dependency: SomeDependency):
        self.dependency = dependency
```

Constructor injection ensures:
- The service is always in a valid state
- Dependencies are immutable after construction
- The dependency graph is explicit

### 3. Keep Services Focused

Each service should have **one clear responsibility**. If a service has too many dependencies (more than 3-4), it's a sign it might be doing too much.

```python
# Warning sign: Too many dependencies
@injectable
class OverwhelmedService:
    def __init__(
        self,
        db: DatabaseService,
        cache: CacheService,
        logger: LoggerService,
        email: EmailService,
        sms: SMSService,
        config: ConfigService,
        auth: AuthService
    ):
        # This service probably has too many responsibilities!
        pass
```

### 4. Explicitly Define Scopes

```python
from fastapi_service import injectable, Scopes

# Configuration - singleton makes sense
@injectable(scope=Scopes.SINGLETON)
class ConfigService:
    def __init__(self):
        self.config = self.load_config()

# Database session - transient is safer
@injectable(scope=Scopes.TRANSIENT)
class DatabaseSession:
    def __init__(self):
        self.connection = self.create_connection()
        # Will be closed after each request

# Service layer
@injectable
class UserService:
    def __init__(self, config: ConfigService, db: DatabaseSession):
        self.config = config  # Singleton
        self.db = db  # Transient - new instance per request
```

## Common DI Anti-Patterns

| Anti-Pattern | Why It's Bad | Better Approach |
|--------------|--------------|-----------------|
| **Service Locator** | Hides dependencies, makes testing hard | Constructor injection |
| **New in Constructor** | Tightly couples to implementation | Inject dependencies |
| **Too Many Dependencies** | Single Responsibility Principle violation | Refactor into smaller services |
| **Using Singletons for Everything** | Can cause state-sharing bugs | Use TRANSIENT for request-scoped data |

## When NOT to Use DI

DI is not a silver bullet. Consider alternatives when:

- **Simple utilities** with no dependencies: Just instantiate directly
- **Data objects** (DTOs, value objects): They shouldn't have injected dependencies
- **Performance-critical paths**: Very tight loops where object creation overhead matters

```python
# Don't use DI for this
class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

# Direct instantiation is fine
point = Point(10, 20)
```

## Relationship to FastAPI's Depends

`fastapi-service` **extends** but doesn't replace `Depends`. You can mix both approaches:

```python
from fastapi import Header, Depends
from fastapi_service import injectable

# Standard FastAPI dependency
def get_user_agent(user_agent: str = Header(default=None)):
    return user_agent

@injectable
class AnalyticsService:
    # Mix @injectable with FastAPI dependencies!
    def __init__(self, user_agent: str = Depends(get_user_agent)):
        self.user_agent = user_agent
    
    def track(self, event: str):
        print(f"[{self.user_agent}] {event}")

@app.post("/events")
async def track_event(
    event: str,
    analytics: AnalyticsService = Depends(AnalyticsService)
):
    analytics.track(event)
    return {"status": "tracked"}
```

This gives you the best of both worlds: automatic service injection AND access to FastAPI's rich dependency ecosystem.

## Summary

Dependency Injection with `fastapi-service` provides:

- **Simplicity**: Just add `@injectable` and type hints
- **Power**: Automatic resolution of complex dependency graphs
- **Safety**: Scope validation prevents lifecycle errors
- **Compatibility**: 100% compatible with FastAPI's native `Depends`
- **Testability**: Easy to mock dependencies in unit tests

The library bridges the gap between manual dependency management and heavyweight DI containers, giving you the right balance of simplicity and power for FastAPI applications.
