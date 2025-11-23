# Plain Object Injection

FastAPI Service can inject dependencies into regular Python classes without requiring the `@injectable` decorator. This is useful for third-party classes, data transfer objects, and simple utility classes.

## When Plain Object Injection Works

Plain object injection works when:

1. The class has a constructor that can be analyzed via type hints
2. All constructor parameters either:
   - Have default values
   - Are registered services (decorated with `@injectable`)
   - Are primitive types with defaults

## Basic Plain Object Injection

```python
# A regular class (no decorator needed)
class SimpleCache:
    def __init__(self, ttl: int = 300):  # Default value allows plain injection
        self.ttl = ttl
        self._cache = {}
    
    def get(self, key: str):
        return self._cache.get(key)
    
    def set(self, key: str, value: str):
        self._cache[key] = value

# Inject plain object into decorated service
@injectable
class UserService:
    def __init__(self, cache: SimpleCache):  # Plain object injected!
        self.cache = cache
    
    def get_user(self, user_id: int):
        cached = self.cache.get(f"user:{user_id}")
        if cached:
            return cached
        # ... fetch from database
        user = {"id": user_id, "name": "John Doe"}
        self.cache.set(f"user:{user_id}", user)
        return user
```

## Complex Dependencies with Plain Objects

```python
# Plain object with multiple dependencies
class WeatherCache:
    def __init__(self, config: ConfigService, ttl: int = 3600):  # Mixed dependencies
        self.config = config
        self.ttl = ttl
        self._cache = {}
    
    def get_weather(self, city: str):
        return self._cache.get(city)
    
    def set_weather(self, city: str, data: dict):
        self._cache[city] = data

@injectable
class WeatherService:
    def __init__(self, cache: WeatherCache):
        self.cache = cache
    
    def get_weather(self, city: str):
        cached = self.cache.get_weather(city)
        if cached:
            return cached
        # ... fetch from API
        weather = {"city": city, "temp": "22°C"}
        self.cache.set_weather(city, weather)
        return weather
```

## Third-Party Class Integration

```python
import httpx
from fastapi_service import injectable

# Third-party class (can't be decorated)
class APIClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout)
        )
    
    async def get(self, endpoint: str):
        response = await self.client.get(endpoint)
        return response.json()

# Adapter pattern for complex setup
@injectable
class ConfiguredAPIClient:
    def __init__(self, config: ConfigService):
        self.client = APIClient(
            base_url=config.get("api_base_url"),
            timeout=config.get("api_timeout", 30)
        )
    
    async def get_user(self, user_id: int):
        return await self.client.get(f"/users/{user_id}")

# Use in service
@injectable
class UserAPIService:
    def __init__(self, api_client: ConfiguredAPIClient):
        self.api_client = api_client
    
    async def fetch_user(self, user_id: int):
        return await self.api_client.get_user(user_id)
```

## Data Transfer Objects (DTOs)

```python
from typing import Optional
from datetime import datetime

# Plain DTO classes
class UserDTO:
    def __init__(self, username: str, email: str, age: Optional[int] = None):
        self.username = username
        self.email = email
        self.age = age
        self.created_at = datetime.now()

class CreateUserRequest:
    def __init__(self, username: str, email: str, password: str):
        self.username = username
        self.email = email
        self.password = password

# Use in FastAPI endpoints
from fastapi import FastAPI, Depends

app = FastAPI()

@app.post("/users")
async def create_user(request: CreateUserRequest = Depends(CreateUserRequest)):
    # FastAPI creates CreateUserRequest from request body
    user_dto = UserDTO(request.username, request.email)
    return {"username": user_dto.username, "email": user_dto.email}
```

## Validation with Plain Objects

```python
from typing import Optional
import re

class ValidatedEmail:
    def __init__(self, email: str):
        if not self._is_valid_email(email):
            raise ValueError(f"Invalid email format: {email}")
        self.email = email
    
    def _is_valid_email(self, email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

class ValidatedUser:
    def __init__(self, username: str, email: ValidatedEmail, age: Optional[int] = None):
        self.username = username
        self.email = email
        self.age = age

@injectable
class UserRegistrationService:
    def __init__(self, email_validator: ValidatedEmail):  # Plain object
        self.email_validator = email_validator
    
    def register_user(self, username: str, email: str):
        try:
            validated_email = ValidatedEmail(email)
            # ... proceed with registration
            return {"username": username, "email": validated_email.email}
        except ValueError as e:
            return {"error": str(e)}
```

## Factory Pattern with Plain Objects

```python
from typing import Protocol

class Logger(Protocol):
    def log(self, message: str): ...

class FileLogger:
    def __init__(self, filename: str = "app.log"):
        self.filename = filename
    
    def log(self, message: str):
        with open(self.filename, "a") as f:
            f.write(f"{message}\n")

class ConsoleLogger:
    def __init__(self, prefix: str = "LOG"):
        self.prefix = prefix
    
    def log(self, message: str):
        print(f"[{self.prefix}] {message}")

# Factory that creates plain objects
@injectable
class LoggerFactory:
    def __init__(self, config: ConfigService):
        self.config = config
    
    def create_logger(self) -> Logger:
        logger_type = self.config.get("logger_type", "console")
        if logger_type == "file":
            return FileLogger(self.config.get("log_file", "app.log"))
        else:
            return ConsoleLogger(self.config.get("log_prefix", "LOG"))

@injectable
class UserService:
    def __init__(self, logger_factory: LoggerFactory):
        self.logger = logger_factory.create_logger()
    
    def create_user(self, username: str):
        self.logger.log(f"Creating user: {username}")
        # ... create user logic
        return {"username": username}
```

## Configuration-Based Plain Objects

```python
# Plain objects configured via dependency injection
class DatabaseConnection:
    def __init__(self, host: str, port: int = 5432, database: str = "myapp"):
        self.host = host
        self.port = port
        self.database = database
        self.connection = None
    
    def connect(self):
        import psycopg2
        self.connection = psycopg2.connect(
            host=self.host,
            port=self.port,
            database=self.database
        )
        return self.connection

# Configuration service provides connection parameters
@injectable
class DatabaseConnectionFactory:
    def __init__(self, config: ConfigService):
        self.config = config
    
    def create_connection(self) -> DatabaseConnection:
        return DatabaseConnection(
            host=self.config.get("db_host", "localhost"),
            port=self.config.get("db_port", 5432),
            database=self.config.get("db_name", "myapp")
        )

@injectable
class UserRepository:
    def __init__(self, connection_factory: DatabaseConnectionFactory):
        self.connection_factory = connection_factory
    
    def get_user(self, user_id: int):
        conn = self.connection_factory.create_connection()
        # ... use connection
        return {"id": user_id, "name": "John Doe"}
```

## Testing with Plain Objects

```python
# test_plain_objects.py
import pytest
from fastapi_service import Container
from your_app import UserService, SimpleCache

def test_service_with_plain_object():
    container = Container()
    
    # Mock the plain object
    class MockCache:
        def __init__(self, ttl: int = 300):
            self.ttl = ttl
            self._data = {}
        
        def get(self, key: str):
            return self._data.get(key)
        
        def set(self, key: str, value: str):
            self._data[key] = value
    
    # Register mock
    container._registry[SimpleCache] = MockCache()
    
    # Resolve service with mocked plain object
    user_service = container.resolve(UserService)
    
    # Test functionality
    user_service.cache.set("user:1", {"id": 1, "name": "John"})
    result = user_service.cache.get("user:1")
    
    assert result == {"id": 1, "name": "John"}
    
    container.clear()
```

## Limitations of Plain Object Injection

### Complex Constructor Logic

```python
# ❌ Won't work - complex constructor logic
class ComplexService:
    def __init__(self, config: ConfigService):
        if config.get("environment") == "production":
            self.backend = "redis"
        else:
            self.backend = "memory"
        # ... more complex logic

# Use factory pattern instead
@injectable
class ComplexServiceFactory:
    def __init__(self, config: ConfigService):
        self.config = config
    
    def create_service(self):
        if self.config.get("environment") == "production":
            return RedisService()
        else:
            return MemoryService()
```

### Circular Dependencies

```python
# ❌ Won't work - circular dependency
class ServiceA:
    def __init__(self, b: ServiceB): pass

class ServiceB:
    def __init__(self, a: ServiceA): pass

# Solution: Use interfaces or refactor
class SharedService: pass

class ServiceA:
    def __init__(self, shared: SharedService): pass

class ServiceB:
    def __init__(self, shared: SharedService): pass
```

### Dynamic Dependencies

```python
# ❌ Won't work - dynamic dependency selection
class DynamicService:
    def __init__(self, service_type: str):
        if service_type == "A":
            self.service = ServiceA()
        else:
            self.service = ServiceB()

# Use factory pattern instead
@injectable
class DynamicServiceFactory:
    def __init__(self, config: ConfigService):
        self.config = config
    
    def create_service(self, service_type: str):
        if service_type == "A":
            return ServiceA()
        else:
            return ServiceB()
```

## Best Practices

### ✅ DO: Use Plain Objects for Simple DTOs

```python
class UserDTO:
    def __init__(self, username: str, email: str):
        self.username = username
        self.email = email
```

### ✅ DO: Use Plain Objects for Third-Party Classes

```python
# Third-party class
class ExternalAPIClient:
    def __init__(self, api_key: str, timeout: int = 30):
        self.api_key = api_key
        self.timeout = timeout
```

### ✅ DO: Provide Defaults for Optional Parameters

```python
class ConfigurableService:
    def __init__(self, required_service: RequiredService, optional_param: str = "default"):
        self.required_service = required_service
        self.optional_param = optional_param
```

### ❌ DON'T: Use Plain Objects for Core Business Services

```python
# ❌ Bad - should use @injectable
class UserService:
    def __init__(self, db: DatabaseService, cache: CacheService):
        self.db = db
        self.cache = cache

# ✅ Good - explicit dependency injection
@injectable
class UserService:
    def __init__(self, db: DatabaseService, cache: CacheService):
        self.db = db
        self.cache = cache
```

### ❌ DON'T: Rely on Plain Objects for Complex Dependencies

```python
# ❌ Bad - complex dependency graph
class ComplexService:
    def __init__(self, a: ServiceA, b: ServiceB, c: ServiceC, d: ServiceD):
        # Too many dependencies to manage manually
        pass

# ✅ Good - use @injectable for complex services
@injectable
class ComplexService:
    def __init__(self, a: ServiceA, b: ServiceB, c: ServiceC, d: ServiceD):
        pass
```

## Summary

Plain object injection is a powerful feature for:

- **Third-party integration**: Use external libraries without modification
- **Simple DTOs**: Data transfer objects and value objects
- **Configuration objects**: Simple configuration classes
- **Validation**: Input validation and sanitization

Use it judiciously alongside `@injectable` for the best balance of simplicity and power.
