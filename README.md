# FastAPI Service

[](https://www.google.com/search?q=https://badge.fury.io/py/fastapi-service)
[](https://opensource.org/licenses/MIT)
[](https://www.python.org/downloads/)

**Effortless Dependency Injection for FastAPI.**

`fastapi-service` is a lightweight, zero-boilerplate dependency injection library designed specifically for FastAPI. It bridges the gap between complex enterprise DI containers and FastAPI's native `Depends` system, making your code cleaner, more testable, and easier to migrate.

## 🚀 Why use this?

FastAPI's dependency injection is powerful, but as your application grows, managing deeply nested dependencies can become verbose. `fastapi-service` solves this by introducing a simple `@injectable` decorator that handles the wiring for you, while staying 100% compatible with standard FastAPI patterns.

### Key Features

  * **Simple APIs**: Just add `@injectable` to your classes. No configuration files, no complex setup.
  * **Deep FastAPI Integration**: Works directly with `Depends()`. No need to learn a new framework.
  * **Support for Plain Classes**: Inject classes you didn't write or don't want to decorate (like third-party libraries).
  * **Gradual Migration**: Adopt it incrementally. Perfect for refactoring legacy codebases without rewriting everything at once.

-----

## 📦 Installation

```bash
pip install fastapi-service
```

-----

## ⚡ Quick Start

### 1\. Define your services

Simply decorate your classes with `@injectable`. Dependencies defined in `__init__` are automatically resolved.

```python
from fastapi_service import injectable

@injectable
class DatabaseService:
    def get_connection(self):
        return "Database Connection"

@injectable
class UserService:
    # DatabaseService is automatically injected!
    def __init__(self, db: DatabaseService):
        self.db = db

    def get_user(self, user_id: int):
        conn = self.db.get_connection()
        return {"id": user_id, "name": "John Doe", "connection": conn}
```

### 2\. Use in FastAPI

Use your services in routes exactly like you would with standard FastAPI dependencies.

```python
from fastapi import FastAPI, Depends
from .services import UserService

app = FastAPI()

@app.get("/users/{user_id}")
def read_user(user_id: int, service: UserService = Depends(UserService)):
    return service.get_user(user_id)
```

-----

## 🔌 Injecting Plain Objects & Third-Party Classes

You don't always have control over the classes you need to use. Whether it's a legacy utility class you can't touch yet, or a client from a third-party library (like `httpx` or `boto3`), `fastapi-service` has you covered.

**You do not need to put `@injectable` on everything.**

If an `@injectable` service depends on a plain class, the library will automatically attempt to instantiate and inject it for you.

```python
# --- legacy_utils.py ---
# This is a plain class. No decorators. 
# Maybe it comes from a library you can't edit!
class SimpleLogger:
    def log(self, message: str):
        print(f"[Legacy Log]: {message}")

# --- services.py ---
from fastapi_service import injectable
from .legacy_utils import SimpleLogger

@injectable
class OrderService:
    # SimpleLogger is NOT decorated, but it is injected automatically.
    def __init__(self, logger: SimpleLogger):
        self.logger = logger

    def create_order(self, item: str):
        self.logger.log(f"Order created for {item}")
```

This feature is incredibly powerful for integrating:

  * **Third-party clients** (e.g., SDKs that don't use injection).
  * **Legacy code** during a gradual refactor.
  * **Data classes** or simple utilities.

-----

## 🔄 Migration Guide (Gradual Adoption)

One of the biggest strengths of `fastapi-service` is its ability to fit into existing projects without breaking changes. You don't need to convert your entire codebase overnight.

### Step 1: The Legacy Codebase

Imagine you have a standard class that isn't using any dependency injection.

```python
# legacy.py
class LegacyEmailSender:
    def send(self, msg):
        print(f"Sending {msg}")
```

### Step 2: The Hybrid Approach

You can write a new service using `@injectable` that depends on the legacy class. Because of the **Plain Object Injection** feature (see above), you don't even need to modify `legacy.py`\!

```python
from fastapi_service import injectable
from .legacy import LegacyEmailSender

@injectable
class NotificationService:
    # LegacyEmailSender is injected automatically without a decorator
    def __init__(self, sender: LegacyEmailSender):
        self.sender = sender 

    def notify(self, message: str):
        self.sender.send(message)
```

### Step 3: Full Modernization

When you are ready, you *can* add `@injectable` to the legacy class if you want it to manage its own dependencies, but it is strictly optional.

-----

## 🧩 Deep Integration with `Depends`

`fastapi-service` is built *on top* of FastAPI's dependency system, not *instead* of it. This means you can mix `@injectable` services with standard FastAPI `Depends` functions.

```python
from fastapi import Header, Depends
from fastapi_service import injectable

# A standard FastAPI dependency function
def get_user_agent(user_agent: str = Header(default=None)):
    return user_agent

@injectable
class AnalyticsService:
    # Injecting a standard FastAPI dependency into a service class!
    def __init__(self, user_agent: str = Depends(get_user_agent)):
        self.user_agent = user_agent

    def log_access(self):
        print(f"Access from: {self.user_agent}")
```

## 🤝 Contributing

Contributions are welcome\! Please read our contributing guidelines to get started.

## 📄 License

This project is licensed under the terms of the MIT license.
