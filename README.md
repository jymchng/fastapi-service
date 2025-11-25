<div align="center">
<p>
<a href="https://fastapi-service.asyncmove.com">
<img src="https://github.com/jymchng/fastapi-service/raw/main/assets/Fastapi-service-with-name_1-1.png" width=80% height=20%></img>
</a>
</p>


<i>Decorate super simple <pre>@injectable</pre> on your FastAPI services.</i>

<hr style="border: none; border-top: 1px solid #ccc; margin: 1em 0;">

<div align="left">
Documentation: <a href="https://docs.fastapi-service.asyncmove.com">
https://docs.fastapi-service.asyncmove.com
</a><br>
Source Code: <a href="https://github.com/jymchng/fastapi-service">
https://github.com/jymchng/fastapi-service
</a>
</div>
<hr style="border: none; border-top: 1px solid #ccc; margin: 1em 0;">

### Compatibility and Version
<img src="https://img.shields.io/pypi/pyversions/fastapi-service?color=green" alt="Python compat">
<a href="https://pypi.python.org/pypi/fastapi-service"><img src="https://img.shields.io/pypi/v/fastapi-service.svg" alt="PyPi"></a>

### Statistics
<a href="https://github.com/jymchng/fastapi-service/stargazers"><img src="https://img.shields.io/github/stars/jymchng/fastapi-service" alt="Stars"></a>
<a href="https://github.com/jymchng/fastapi-service/network/members"><img src="https://img.shields.io/github/forks/jymchng/fastapi-service" alt="Forks"></a>
<a href="https://pypi.python.org/pypi/fastapi-service"><img src="https://img.shields.io/pypi/dm/fastapi-service" alt="Downloads"></a>
<a href="https://github.com/jymchng/fastapi-service/graphs/contributors"><img src="https://img.shields.io/github/contributors/jymchng/fastapi-service" alt="Contributors"></a>

### Development and Quality
<a href="https://github.com/jymchng/fastapi-service/commits/main"><img src="https://img.shields.io/github/commit-activity/m/jymchng/fastapi-service" alt="Commits"></a>
<a href="https://github.com/jymchng/fastapi-service/commits/main"><img src="https://img.shields.io/github/last-commit/jymchng/fastapi-service" alt="Last Commit"></a>
<a href="https://github.com/jymchng/fastapi-service"><img src="https://img.shields.io/github/languages/code-size/jymchng/fastapi-service" alt="Code Size"></a>
<a href="https://github.com/jymchng/fastapi-service"><img src="https://img.shields.io/github/repo-size/jymchng/fastapi-service" alt="Repo Size"></a>
<a href="https://github.com/jymchng/fastapi-service/watchers"><img src="https://img.shields.io/github/watchers/jymchng/fastapi-service" alt="Watchers"></a>
<a href="https://github.com/jymchng/fastapi-service"><img src="https://img.shields.io/github/commit-activity/y/jymchng/fastapi-service" alt="Activity"></a>
<a href="https://github.com/jymchng/fastapi-service/pulls"><img src="https://img.shields.io/github/issues-pr/jymchng/fastapi-service" alt="PRs"></a>
<a href="https://github.com/jymchng/fastapi-service/pulls?q=is%3Apr+is%3Aclosed"><img src="https://img.shields.io/github/issues-pr-closed/jymchng/fastapi-service" alt="Merged PRs"></a>
<a href="https://github.com/jymchng/fastapi-service/pulls?q=is%3Apr+is%3Aopen"><img src="https://img.shields.io/github/issues-pr/open/jymchng/fastapi-service" alt="Open PRs"></a>
<a href="https://github.com/jymchng/fastapi-service/issues?q=is%3Aissue+is%3Aclosed"><img src="https://img.shields.io/github/issues-closed/jymchng/fastapi-service" alt="Closed Issues"></a>
<a href="https://github.com/jymchng/fastapi-service/blob/main/LICENSE"><img src="https://img.shields.io/github/license/jymchng/fastapi-service" alt="License"></a>
<a href="https://codecov.io/github/jymchng/fastapi-service?branch=main"><img src="https://codecov.io/github/jymchng/fastapi-service/coverage.svg?branch=main" alt="Coverage"></a>

</div>
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

PIP
```bash
pip install fastapi-service
```

UV
```bash
uv add fastapi-service
```

POETRY
```bash
poetry add fastapi-service
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

-----

## 🛡️ Scopes & Scope Safety

`fastapi-service` provides robust scope management to ensure your application's lifecycle is handled correctly. We support two primary scopes:

  * **`Scopes.TRANSIENT` (Default):** A new instance is created for every injection. This is standard FastAPI behavior.
  * **`Scopes.SINGLETON`:** The same instance is shared across the entire application lifetime.

### Preventing "Scope Leaks"

A common pitfall in dependency injection is injecting a short-lived object (Transient) into a long-lived object (Singleton). This causes the short-lived object to "live forever" inside the singleton, often leading to stale database sessions or thread-safety issues.

`fastapi-service` **validates your dependency graph at runtime**. When a service is requested, the library checks the entire chain. If you attempt to inject a `TRANSIENT` service into a `SINGLETON` service, it will detect the mismatch and raise an error, preventing unstable behavior.

```python
from fastapi_service import injectable, Scopes

# ❌ ERROR: You cannot inject this Transient service...
@injectable(scope=Scopes.TRANSIENT)
class DatabaseSession:
    pass

# ...into this Singleton service.
@injectable(scope=Scopes.SINGLETON)
class GlobalCache:
    def __init__(self, session: DatabaseSession):
        self.session = session
```

**Correct Usage:**
Singletons should only depend on other Singletons or stateless configurations.

```python
@injectable(scope=Scopes.SINGLETON)
class ConnectionPool:
    pass

@injectable(scope=Scopes.SINGLETON)
class UserRepository:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
```

-----

## 🔧 Under the Hood: Technical Architecture

`fastapi-service` is designed to be a **structural analyzer** that leverages Python's native metaprogramming capabilities to prepare your classes for FastAPI's dependency resolution system.

Here is the step-by-step breakdown of the injection lifecycle:

### 1\. Introspection & Registration

When you decorate a class with `@injectable`, the library utilizes Python's `inspect` module and `typing.get_type_hints` to analyze the `__init__` constructor. It registers the class and its type hints, preparing them for future resolution.

### 2\. Dynamic Signature Rewriting (The "Magic")

This is the core mechanism that enables integration with FastAPI. `fastapi-service` dynamically generates a **factory function** for each service.

The library constructs a new `inspect.Signature` for this factory, programmatically inserting `fastapi.Depends(...)` into the default values of the function parameters.

Essentially, it automates the translation from:

```python
# Your clean code
class UserService:
    def __init__(self, db: Database): ...
```

To the verbose definition FastAPI expects:

```python
# What FastAPI sees internally
def user_service_factory(db: Database = Depends(database_factory)):
    return UserService(db=db)
```

### 3\. Runtime Graph Resolution & Validation

Currently, validation occurs dynamically at runtime during the dependency resolution phase.

  * **Scope Safety:** When a dependency is instantiated, the library verifies that no `Scopes.SINGLETON` service is attempting to hold onto a `Scopes.TRANSIENT` service.
  * **Cycle Detection:** Standard Python recursion limits and dependency resolution mechanics naturally prevent infinite loops.

*Note: Future versions of `fastapi-service` aim to move these validations to build-time (startup) to catch configuration errors even earlier.*

### 4\. Native Execution Strategy

Because the library translates your structure into standard FastAPI dependency chains, you retain all the performance benefits of FastAPI's asynchronous execution model. The "magic" happens only during the wiring phase; the execution is pure FastAPI.

## 🤝 Contributing

Contributions are welcome\! Please read our contributing guidelines to get started.

## 📄 License

This project is licensed under the terms of the MIT license.
