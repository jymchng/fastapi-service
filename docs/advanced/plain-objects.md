# Plain Object Injection

Plain Object Injection is a powerful feature that lets you inject **classes without the `@injectable` decorator**. This is essential for integrating third-party libraries, legacy code, and classes you don't control.

## What is Plain Object Injection?

Plain Object Injection automatically resolves and injects classes **not** decorated with `@injectable`. The library analyzes the class constructor, inspects type hints, and resolves dependencies dynamically.

### Key Difference: Decorated vs Plain Classes

```python
# Decorated class (explicit opt-in)
@injectable
class ExplicitService:
    def __init__(self, db: DatabaseService):
        self.db = db

# Plain class (auto-detected)
class PlainService:
    def __init__(self, db: DatabaseService):
        self.db = db

@injectable
class ConsumerService:
    def __init__(self, explicit: ExplicitService, plain: PlainService):
        self.explicit = explicit
        self.plain = plain  # PlainService is injected automatically!
```

**Why this matters**: You can't add `@injectable` to classes from external libraries or legacy codebases. Plain Object Injection solves this without wrappers or adapters.

## When Plain Injection Works

Plain injection works when these conditions are met:

### 1. Type Hints Are Required

```python
# ✅ Works: Type hints present
class ValidService:
    def __init__(self, db: DatabaseService, cache: CacheService):
        self.db = db
        self.cache = cache

@injectable
class Consumer:
    def __init__(self, service: ValidService):  # Auto-injected
        self.service = service

# ❌ Fails: Missing type hints
class InvalidService:
    def __init__(self, database):  # No type hint!
        self.db = database

@injectable
class BadConsumer:
    def __init__(self, service: InvalidService):  # Error: Cannot resolve
        self.service = service
```

### 2. Primitive Types Need Default Values

```python
# ✅ Works: Primitives have defaults
class ConfiguredService:
    def __init__(self, db: DatabaseService, timeout: int = 30):
        self.db = db
        self.timeout = timeout

# ❌ Fails: Primitive without default
class BrokenService:
    def __init__(self, db: DatabaseService, timeout: int):  # No default!
        self.db = db
        self.timeout = timeout

@injectable
class Consumer:
    def __init__(self, service: BrokenService):  # Error: Cannot resolve 'timeout'
        self.service = service
```

### 3. Dependencies Must Be Injectable or Plain-Resolvable

```python
@injectable
class DatabaseService: pass

# ✅ Works: Depends on injectable service
class Repository:
    def __init__(self, db: DatabaseService):
        self.db = db

@injectable
class Service:
    def __init__(self, repo: Repository):  # Repository is auto-injected
        self.repo = repo
```

## Common Use Cases

### 1. Third-Party Library Classes

```python
import httpx
from fastapi_service import injectable

# httpx.AsyncClient has no @injectable decorator
# But we can inject it automatically!
@injectable
class APIClient:
    def __init__(self, config: ConfigService):
        # httpx.AsyncClient uses plain injection
        self.client = httpx.AsyncClient(
            base_url=config.get("api_url"),
            timeout=httpx.Timeout(30.0)
        )
    
    async def get(self, endpoint: str):
        return await self.client.get(endpoint)

@injectable
class UserService:
    def __init__(self, api: APIClient):
        self.api = api
    
    async def fetch_user(self, user_id: int):
        return await self.api.get(f"/users/{user_id}")
```

### 2. Legacy Code Integration

```python
# legacy_module.py (cannot modify)
class LegacyLogger:
    def __init__(self, log_file: str = "app.log"):  # Has default
        self.log_file = log_file
    
    def log(self, message: str):
        with open(self.log_file, "a") as f:
            f.write(message + "\n")

# services.py (your new code)
from fastapi_service import injectable
from legacy_module import LegacyLogger

@injectable
class UserService:
    def __init__(self, logger: LegacyLogger):  # Auto-injects LegacyLogger!
        self.logger = logger
    
    def create_user(self, name: str):
        self.logger.log(f"Creating user: {name}")
        return {"name": name}
```

### 3. Data Transfer Objects (DTOs)

```python
# DTOs often don't need decorators
class UserDTO:
    def __init__(self, name: str, email: str, age: int = 0):
        self.name = name
        self.email = email
        self.age = age

@injectable
class UserService:
    def __init__(self, db: DatabaseService):
        self.db = db
    
    def get_user_dto(self, user_id: int) -> UserDTO:
        data = self.db.query("SELECT * FROM users WHERE id = ?", user_id)
        # UserDTO can be auto-injected elsewhere if needed
        return UserDTO(name=data["name"], email=data["email"], age=data["age"])
```

## How It Works: Auto-Resolution Process

Plain injection uses runtime introspection:

```python
class PlainClass:
    def __init__(self, service: DatabaseService, timeout: int = 30):
        self.service = service
        self.timeout = timeout

# When resolving PlainClass:
# 1. Inspect __init__ signature
# 2. Get type hints: {'service': DatabaseService, 'timeout': int}
# 3. For 'service': resolve DatabaseService (recursive)
# 4. For 'timeout': use default value 30 (no type to resolve)
# 5. Call PlainClass(service=resolved_db, timeout=30)
```

**Key insight**: The `Container._auto_resolve` method handles this transparently.

## Limitations and Important Caveats

### 1. Always Transient Scope

```python
# Plain classes are ALWAYS TRANSIENT scope
class PlainService:
    def __init__(self): pass

@injectable(scope=Scopes.SINGLETON)
class SingletonConsumer:
    def __init__(self, plain: PlainService):  # ❌ SCOPE ERROR!
        self.plain = plain  # Would trap transient in singleton

# ERROR: Cannot inject non-singleton-scoped dependency 'PlainService' into singleton-scoped 'SingletonConsumer'
```

**Rule**: Plain classes cannot be injected into SINGLETON services because their scope is unknown and defaults to TRANSIENT.

**Solution**: Make both singleton or both transient:

```python
# Option A: Both transient
@injectable(scope=Scopes.TRANSIENT)
class SafeConsumer:
    def __init__(self, plain: PlainService):
        self.plain = plain  # ✅ Both transient

# Option B: Decorate the plain class
@injectable(scope=Scopes.SINGLETON)
class NowSingleton:
    def __init__(self): pass

@injectable(scope=Scopes.SINGLETON)
class SafeConsumer:
    def __init__(self, singleton: NowSingleton):
        self.singleton = singleton  # ✅ Both singleton
```

### 2. No Scope Validation for Plain Dependencies

```python
@injectable(scope=Scopes.SINGLETON)
class ConfigService: pass

class PlainRepository:
    def __init__(self, config: ConfigService):  # ✅ Works: config is singleton
        self.config = config

@injectable
class Service:
    def __init__(self, repo: PlainRepository):  # ⚠️ No scope validation!
        self.repo = repo
```

**The plain class `PlainRepository` could hold a reference to a TRANSIENT service without the system detecting it.** Decorated classes have scope safety; plain classes do not.

### 3. No Token-based Resolution

Plain classes cannot use token-based registration:

```python
from fastapi_service import register_injectable

# This doesn't work for plain classes
register_injectable("special_service", SomePlainClass)  # ❌ Plain classes have no token support

# Only decorated classes support tokens
@injectable(token="special_service")
class SpecialService: pass
```

## Best Practices

### ✅ DO: Use @injectable for Your Services

```python
# ✅ Good: Your services are explicit
@injectable
class UserService:
    def __init__(self, db: DatabaseService):
        self.db = db
```

### ✅ DO: Use Plain Injection for External Code

```python
# ✅ Good: External class, can't modify
import redis

class RedisCache:
    def __init__(self, host: str = "localhost", port: int = 6379):
        self.client = redis.Redis(host=host, port=port)
```

### ❌ DON'T: Mix Scopes Unsafely

```python
# ❌ Danger: Plain class injected into singleton
@injectable(scope=Scopes.SINGLETON)
class UnsafeSingleton:
    def __init__(self, plain: PlainCache):  # PlainCache is transient
        self.cache = plain  # Will cause stale data
```

### ✅ DO: Document Plain Dependencies

```python
@injectable
class UserService:
    def __init__(self, db: DatabaseService, cache: "PlainCache"):
        """
        Args:
            db: Injected database service
            cache: Plain RedisCache instance (auto-resolved, transient)
        """
        self.db = db
        self.cache = cache
```

### ✅ DO: Provide Defaults for Configuration

```python
# ✅ Good: Configurable via defaults
class ConfigurableService:
    def __init__(
        self,
        db: DatabaseService,
        timeout: int = 30,
        retries: int = 3,
        endpoint: str = "https://api.example.com"
    ):
        self.db = db
        self.timeout = timeout
        self.retries = retries
        self.endpoint = endpoint

@injectable
class Consumer:
    def __init__(self, service: ConfigurableService):
        # Uses all defaults
        self.service = service
```

## Testing with Plain Objects

### Override Plain Classes in Tests

```python
# conftest.py
import pytest
from fastapi_service import Container
from legacy import PlainLogger

class MockLogger:
    def log(self, message: str):
        self.last_message = message

@pytest.fixture
def test_container():
    container = Container()
    # Override plain class with mock
    container._registry[PlainLogger] = MockLogger()
    yield container
    container.clear()

# test_service.py
def test_with_mock_logger(test_container):
    from services import UserService
    
    service = test_container.resolve(UserService)
    service.logger.log("test")
    assert service.logger.last_message == "test"
```

### Test Plain Classes Directly

```python
def test_plain_service():
    # Mock dependencies manually
    mock_db = MockDatabase()
    
    # Create plain instance directly
    plain_service = PlainService(db=mock_db, timeout=10)
    
    assert plain_service.timeout == 10
    assert plain_service.db is mock_db
```

## Performance Comparison

### Decorated vs Plain Resolution

```python
# Decorated service (cached metadata)
@injectable
class DecoratedService:
    def __init__(self, db: DatabaseService): pass

# Plain service (metadata extracted each time)
class PlainService:
    def __init__(self, db: DatabaseService): pass

# First resolution:
decorated = container.resolve(DecoratedService)  # ~0.05ms (cached metadata)
plain = container.resolve(PlainService)          # ~0.08ms (extract metadata)

# Subsequent resolutions:
decorated = container.resolve(DecoratedService)  # ~0.05ms
plain = container.resolve(PlainService)          # ~0.08ms (no caching)
```

**Difference**: Negligible (~0.03ms) for most applications. Use `@injectable` for your core services, plain injection for integration.

## Migration Strategy: Plain to Decorated

### Step 1: Start with Plain (Legacy)

```python
# Old code in legacy.py
class LegacyService:
    def __init__(self, db: DatabaseService):
        self.db = db
```

### Step 2: Use Plain Injection (Bridge)

```python
# New code in services.py
from fastapi_service import injectable
from legacy import LegacyService

@injectable
class ModernService:
    def __init__(self, legacy: LegacyService):
        self.legacy = legacy  # Plain injection works!
```

### Step 3: Migrate to Decorated (Final)

```python
# After refactoring legacy.py
from fastapi_service import injectable

@injectable  # Now decorated!
class LegacyService:
    def __init__(self, db: DatabaseService):
        self.db = db

# services.py remains unchanged - zero breaking changes!
```

## Debugging Plain Injection

### Enable Verbose Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# When resolving plain classes, you'll see:
# DEBUG: Auto-resolving PlainClass
# DEBUG: Parameter 'service' -> type DatabaseService
# DEBUG: Resolving DatabaseService...
# DEBUG: Parameter 'timeout' -> using default 30
```

### Inspect Resolution

```python
from fastapi_service import Container

container = Container()

# Check if class will be auto-resolved
def can_auto_resolve(cls):
    try:
        container.resolve(cls)
        return True
    except Exception as e:
        print(f"Cannot resolve {cls.__name__}: {e}")
        return False

print(can_auto_resolve(PlainService))  # True or False with reason
```

## Summary: When to Use Plain Injection

| Scenario | Plain Injection | @injectable |
|----------|----------------|-------------|
| Your application services | ❌ No (use explicit) | ✅ Yes |
| Third-party libraries | ✅ Yes | ❌ No (can't modify) |
| Legacy code | ✅ Yes | ❌ No (can't modify) |
| Simple DTOs/Value objects | ✅ Yes | ⚠️ Optional |
| Need SINGLETON scope | ❌ No (always TRANSIENT) | ✅ Yes |
| Need scope validation | ❌ No | ✅ Yes |
| Need token-based resolution | ❌ No | ✅ Yes |

**Rule of thumb**: Use `@injectable` for services you own. Use plain injection for code you don't control.
