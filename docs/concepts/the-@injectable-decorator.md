# The `@injectable` Decorator

The `@injectable` decorator is the primary API for enabling dependency injection in your FastAPI applications. It transforms a regular class into an automatically resolvable dependency.

## Basic Usage

Add `@injectable` to any class to make it available for automatic dependency resolution:

```python
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
```

Use in FastAPI endpoints:

```python
from fastapi import FastAPI, Depends
from services import UserService

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, service: UserService = Depends(UserService)):
    return service.get_user(user_id)
```

**Key principle**: Just reference the class directly in `Depends()` - the decorator handles all wiring automatically.

## Specifying Scope

Control instance lifecycle with the `scope` parameter:

```python
from fastapi_service import injectable, Scopes

# Single instance for entire application
@injectable(scope=Scopes.SINGLETON)
class ConfigService:
    def __init__(self):
        self.config = self._load_from_file()

# New instance per request (default)
@injectable(scope=Scopes.TRANSIENT)  # or just @injectable
class DatabaseSession:
    def __init__(self, config: ConfigService):
        self.connection = self._connect(config.config["db_url"])
```

**Scope Safety**: The system prevents scope leaks:

```python
# ❌ Raises ValueError at runtime
@injectable(scope=Scopes.SINGLETON)
class GlobalCache:
    def __init__(self, session: DatabaseSession):  # DatabaseSession is TRANSIENT
        self.session = session  # Would trap session forever
```

## Automatic Resolution of Dependencies

### Simple Chains

Dependencies are resolved recursively based on type hints:

```python
@injectable
class LoggerService:
    def log(self, message: str): pass

@injectable
class AuditService:
    def __init__(self, logger: LoggerService):
        self.logger = logger

@injectable
class UserService:
    def __init__(self, audit: AuditService, db: DatabaseSession):
        self.audit = audit
        self.db = db
```

When you use `Depends(UserService)`, the system automatically resolves: `UserService → AuditService → LoggerService` and `UserService → DatabaseSession`.

### Complex Graphs

The system handles complex dependency graphs without configuration:

```python
@injectable(scope=Scopes.SINGLETON)
class ConfigService:
    def get(self, key: str): pass

@injectable
class CacheService:
    def __init__(self, config: ConfigService): pass

@injectable
class DatabaseService:
    def __init__(self, config: ConfigService): pass

@injectable
class RepositoryService:
    def __init__(self, db: DatabaseService, cache: CacheService): pass

@injectable
class UserService:
    def __init__(self, repo: RepositoryService): pass
```

All dependencies are resolved automatically with proper scope management.

## Working with Third-Party Classes

### Plain Object Injection

Undecorated classes can be injected if they have resolvable constructors:

```python
# Third-party class (no decorator needed)
class SimpleCache:
    def __init__(self, ttl: int = 300):  # Must have defaults or resolvable deps
        self.ttl = ttl

@injectable
class UserService:
    def __init__(self, cache: SimpleCache):  # Auto-injected!
        self.cache = cache
```

### When Plain Injection Works

- Primitive types (int, str, etc.) must have default values
- Complex types are recursively resolved
- Constructor must be analyzable via type hints

### Adapter Pattern for Complex Cases

For third-party classes that need complex setup:

```python
import httpx
from fastapi_service import injectable

@injectable
class APIClientAdapter:
    def __init__(self, config: ConfigService):
        self.client = httpx.AsyncClient(
            base_url=config.get("api_url"),
            timeout=httpx.Timeout(30.0)
        )
    
    async def get(self, endpoint: str):
        return await self.client.get(endpoint)
```

## Integration with FastAPI Dependencies

### Mixing with Standard Depends

Combine `@injectable` with FastAPI's dependency system:

```python
from fastapi import Header, Depends

def get_user_agent(user_agent: str = Header(default=None)):
    return user_agent

@injectable
class AnalyticsService:
    def __init__(self, user_agent: str = Depends(get_user_agent)):
        self.user_agent = user_agent
    
    def track(self, event: str):
        print(f"[{self.user_agent}] {event}")
```

### Accessing the Request Object

```python
from fastapi import Request

@injectable
class RequestContextService:
    def __init__(self, request: Request):  # Request is injected automatically
        self.request = request
    
    def get_client_ip(self):
        return self.request.client.host if self.request.client else None
    
    def get_headers(self):
        return self.request.headers
```

## Testing with Dependency Overrides

The library provides `Container` for test isolation:

```python
# conftest.py
import pytest
from fastapi_service import Container

@pytest.fixture
def container():
    c = Container()
    yield c
    c.clear()  # Clean up after each test

# test_services.py
def test_user_service_with_mock_db(container):
    # Create mock
    class MockDatabase:
        def get_connection(self):
            return "Mock Connection"
    
    # Register mock in container
    container._registry[DatabaseService] = MockDatabase()
    
    # Resolve service - will inject mock
    user_service = container.resolve(UserService)
    
    assert user_service.db.get_connection() == "Mock Connection"
```

### Override Pattern for Integration Tests

```python
# test_endpoints.py
from fastapi.testclient import TestClient
from fastapi import FastAPI
from fastapi_service import Container

def test_endpoint_with_overrides():
    app = FastAPI()
    container = Container()
    
    # Override dependencies
    class TestConfig:
        def get(self, key: str):
            return "test-value"
    
    container._registry[ConfigService] = TestConfig()
    
    @app.get("/test")
    def test_endpoint(config: ConfigService = Depends(ConfigService)):
        return {"value": config.get("key")}
    
    client = TestClient(app)
    response = client.get("/test")
    assert response.json() == {"value": "test-value"}
    
    container.clear()
```

## Common Patterns

### Configuration Service

```python
@injectable(scope=Scopes.SINGLETON)
class ConfigService:
    def __init__(self, env: str = "development"):
        self.env = env
        self._config = self._load_config()
    
    def get(self, key: str, default=None):
        return self._config.get(key, default)
    
    def _load_config(self):
        # Load from file, env vars, etc.
        return {"db_url": "postgres://...", "api_key": "secret"}
```

### Repository Pattern

```python
@injectable
class UserRepository:
    def __init__(self, db: DatabaseSession):
        self.db = db
    
    def get_by_id(self, user_id: int):
        return self.db.query("SELECT * FROM users WHERE id = ?", user_id)
    
    def save(self, user: dict):
        return self.db.execute("INSERT INTO users ...", user)

@injectable
class UserService:
    def __init__(self, repo: UserRepository, cache: CacheService):
        self.repo = repo
        self.cache = cache
    
    def get_user(self, user_id: int):
        cached = self.cache.get(f"user:{user_id}")
        if cached:
            return cached
        
        user = self.repo.get_by_id(user_id)
        self.cache.set(f"user:{user_id}", user)
        return user
```

### Event Handlers and Background Tasks

```python
@injectable
class EmailService:
    def send(self, to: str, subject: str, body: str): pass

@injectable
class NotificationService:
    def __init__(self, email: EmailService):
        self.email = email
    
    def notify_user(self, user_id: int, message: str):
        # Queue background task or send immediately
        self.email.send(f"user_{user_id}@example.com", "Notification", message)

@injectable
class OrderService:
    def __init__(self, notifier: NotificationService):
        self.notifier = notifier
    
    def create_order(self, user_id: int, items: list):
        # Create order logic...
        self.notifier.notify_user(user_id, f"Order created: {len(items)} items")
        return {"status": "success", "order_id": 123}
```

## Error Handling and Validation

### Missing Type Hints

```python
# ❌ Will fail
@injectable
class BadService:
    def __init__(self, database):  # No type hint
        self.db = database

# ✅ Correct
@injectable
class GoodService:
    def __init__(self, database: DatabaseService):  # Type hint provided
        self.db = database
```

### Unresolvable Dependencies

```python
# ❌ Will raise ValueError
@injectable
class BadService:
    def __init__(self, missing: SomeUndefinedType):  # Type not registered
        self.missing = missing

# Solution: Register the type or provide a default
@injectable
class GoodService:
    def __init__(self, missing: SomeUndefinedType = None):  # Optional with default
        self.missing = missing or DefaultImplementation()
```

### Circular Dependencies

```python
# ❌ Will fail with circular dependency error
@injectable
class ServiceA:
    def __init__(self, b: ServiceB): pass

@injectable
class ServiceB:
    def __init__(self, a: ServiceA): pass

# Solution: Extract common dependencies
@injectable
class SharedService: pass

@injectable
class ServiceA:
    def __init__(self, shared: SharedService): pass

@injectable
class ServiceB:
    def __init__(self, shared: SharedService): pass
```

## Performance Considerations

### Singleton for Expensive Resources

```python
@injectable(scope=Scopes.SINGLETON)
class MLModelService:
    def __init__(self):
        # This runs once at startup
        self.model = self._load_large_model()  # Expensive operation
    
    def predict(self, data):
        return self.model.infer(data)
```

### Transient for Request-Scoped Data

```python
@injectable  # TRANSIENT by default
class RequestTimer:
    def __init__(self):
        self.start = time.time()
    
    def elapsed(self):
        return time.time() - self.start

@injectable
class PerformanceService:
    def __init__(self, timer: RequestTimer):
        self.timer = timer
    
    def log_duration(self, operation: str):
        print(f"{operation} took {self.timer.elapsed():.3f}s")
```

## Advanced Configuration

### Conditional Registration

```python
import os
from fastapi_service import injectable

if os.getenv("TESTING"):
    # Use test implementation in test environment
    @injectable
    class EmailService:
        def send(self, to, subject, body):
            print(f"[TEST] Email to {to}: {subject}")
else:
    # Use production implementation
    @injectable
    class EmailService:
        def send(self, to, subject, body):
            # Real SMTP logic
            pass
```

### Using Container Directly

For advanced scenarios, use the `Container` class:

```python
from fastapi_service import Container

container = Container()

# Manual resolution
config = container.resolve(ConfigService)

# Check if injectable
if container.get_metadata(UserService):
    print("UserService is registered")

# Clear state (useful in tests)
container.clear()
```

## Best Practices

### ✅ DO: Keep constructors lightweight

```python
@injectable
class GoodService:
    def __init__(self, db: DatabaseService):
        self.db = db
    
    def initialize(self):
        # Heavy lifting done explicitly, not in constructor
        self.connection = self.db.connect()
```

### ❌ DON'T: Perform heavy work in constructors

```python
@injectable  # ❌ Bad for TRANSIENT scope
class BadService:
    def __init__(self):
        self.data = self._load_huge_dataset()  # Slow!
```

### ✅ DO: Use explicit type hints

```python
@injectable
class GoodService:
    def __init__(self, db: DatabaseService):  # Clear type
        self.db = db
```

### ❌ DON'T: Omit type hints

```python
@injectable
class BadService:
    def __init__(self, database):  # ❌ No type hint
        self.db = database  # Won't inject
```

### ✅ DO: Limit dependencies per service

```python
@injectable
class GoodService:
    def __init__(self, repo: Repository, cache: CacheService):
        # 2-3 dependencies is reasonable
        self.repo = repo
        self.cache = cache
```

### ❌ DON'T: Create "god objects"

```python
@injectable
class BadService:
    def __init__(self, dep1, dep2, dep3, dep4, dep5, dep6, dep7):
        # Too many responsibilities!
        pass
```

## Troubleshooting Guide

### "Type hint is missing"

**Problem**: Constructor parameter without type annotation
**Solution**: Add type hints to all injected parameters

### "Cannot inject non-singleton-scoped dependency into singleton"

**Problem**: Scope leak - injecting TRANSIENT into SINGLETON
**Solution**: Change scopes or refactor to avoid storing transient in singleton

### "Circular dependency detected"

**Problem**: A depends on B, B depends on A
**Solution**: Extract common logic into a third service

### "Cannot resolve dependency"

**Problem**: Type not registered or unresolvable
**Solution**: Ensure type is decorated with `@injectable` or provide default value

---

**Next: [Advanced Usage → Plain Object Injection](../advanced/plain-objects.md)**
