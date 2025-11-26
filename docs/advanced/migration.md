# Legacy Migration Guide

One of the most powerful features of `fastapi-service` is **gradual migration** - you can adopt it incrementally without rewriting your entire codebase. This guide shows how to migrate from legacy, non-DI code to modern dependency injection in three phases.

## Phase 1: The Legacy Codebase (No DI)

Let's start with a typical FastAPI application without dependency injection:

```python
# legacy_database.py
import sqlite3

class Database:
    def __init__(self, db_path: str = "./app.db"):
        self.db_path = db_path
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def get_user(self, user_id: int):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            return cursor.fetchone()
        finally:
            conn.close()

# legacy_email.py
import smtplib

class EmailSender:
    def __init__(self, smtp_server: str = "localhost"):
        self.smtp_server = smtp_server
    
    def send(self, to: str, subject: str, body: str):
        # Simplified - real implementation would be more robust
        with smtplib.SMTP(self.smtp_server) as server:
            server.sendmail("app@example.com", [to], f"Subject: {subject}\n\n{body}")

# main.py
from fastapi import FastAPI
from legacy_database import Database
from legacy_email import EmailSender

app = FastAPI()
db = Database()  # Global instance
email = EmailSender()  # Global instance

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    # Direct instantiation - hard to test
    user = db.get_user(user_id)
    if user:
        email.send(user.email, "Welcome", "Thanks for using our service")
    return user

# Problems:
# 1. Tight coupling - hard to swap implementations
# 2. Hard to test - can't mock dependencies
# 3. No lifecycle management
# 4. Global state
```

## Phase 2: Hybrid Approach (Start Using @injectable)

Introduce `fastapi-service` without touching legacy code. The **Plain Object Injection** feature is key here.

```python
# Step 1: Install fastapi-service
# pip install fastapi-service

# Step 2: Create a new service using @injectable that depends on legacy classes
# services/notification_service.py
from fastapi_service import injectable
from legacy_email import EmailSender
from legacy_database import Database

@injectable
class NotificationService:
    def __init__(self, db: Database, email: EmailSender):
        # Legacy classes are automatically injected!
        self.db = db
        self.email = email
    
    def notify_user(self, user_id: int, message: str):
        user = self.db.get_user(user_id)
        if user:
            self.email.send(
                to=user["email"],
                subject="Notification",
                body=message
            )
            return True
        return False

# Step 3: Use it in your FastAPI app
# main_v2.py
from fastapi import FastAPI, Depends
from services.notification_service import NotificationService

app = FastAPI()

@app.post("/notify/{user_id}")
async def notify_user(user_id: int, notifier: NotificationService = Depends(NotificationService)):
    success = notifier.notify_user(user_id, "You have a new message!")
    return {"notified": success}

# Benefits:
# 1. No changes to legacy code
# 2. New code is clean and testable
# 3. Can mock dependencies in tests
# 4. Starts the migration path
```

### Testing the Hybrid Approach

```python
# tests/test_notification_service.py
import pytest
from fastapi_service import Container
from services.notification_service import NotificationService
from legacy_database import Database
from legacy_email import EmailSender

class MockDatabase:
    def get_user(self, user_id: int):
        if user_id == 1:
            return {"id": 1, "email": "test@example.com"}
        return None

class MockEmailSender:
    def __init__(self):
        self.sent_emails = []
    
    def send(self, to: str, subject: str, body: str):
        self.sent_emails.append({"to": to, "subject": subject, "body": body})

@pytest.fixture
def container():
    from fastapi_service import Container
    c = Container()
    yield c
    c.clear()

def test_notification_sends_email(container):
    # Override legacy dependencies with mocks
    container._registry[Database] = MockDatabase()
    container._registry[EmailSender] = MockEmailSender()
    
    # Resolve service - mocks are injected
    notifier = container.resolve(NotificationService)
    
    # Test logic
    result = notifier.notify_user(1, "Test message")
    assert result is True
    
    email_sender = container.resolve(EmailSender)
    assert len(email_sender.sent_emails) == 1
    assert email_sender.sent_emails[0]["to"] == "test@example.com"

def test_notification_user_not_found(container):
    container._registry[Database] = MockDatabase()
    container._registry[EmailSender] = MockEmailSender()
    
    notifier = container.resolve(NotificationService)
    result = notifier.notify_user(999, "Test message")
    assert result is False
```

## Phase 3: Full Modernization (Optional)

As you rewrite legacy modules, add `@injectable` to them. The beauty: **zero breaking changes** to services that depend on them.

```python
# Step 1: Refactor legacy_database.py
# legacy_database.py (now using DI)
from fastapi_service import injectable, Scopes

@injectable(scope=Scopes.SINGLETON)  # Now a managed singleton!
class Database:
    def __init__(self, config: ConfigService):  # Now depends on ConfigService
        self.config = config
    
    def get_connection(self):
        import sqlite3
        return sqlite3.connect(self.config.get("db_path", "./app.db"))
    
    def get_user(self, user_id: int):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            return cursor.fetchone()
        finally:
            conn.close()

# Step 2: Refactor legacy_email.py
# legacy_email.py
from fastapi_service import injectable, Scopes

@injectable(scope=Scopes.SINGLETON)
class EmailSender:
    def __init__(self, config: ConfigService):
        self.config = config
    
    def send(self, to: str, subject: str, body: str):
        import smtplib
        smtp_server = self.config.get("smtp_server", "localhost")
        with smtplib.SMTP(smtp_server) as server:
            server.sendmail(
                self.config.get("from_email", "app@example.com"),
                [to],
                f"Subject: {subject}\n\n{body}"
            )

# Step 3: Add ConfigService
# services/config_service.py
from fastapi_service import injectable, Scopes

@injectable(scope=Scopes.SINGLETON)
class ConfigService:
    def __init__(self, env: str = "development"):
        self.env = env
    
    def get(self, key: str, default=None):
        # In real app, load from file, env vars, etc.
        config = {
            "db_path": "./app.db",
            "smtp_server": "localhost",
            "from_email": "app@example.com"
        }
        return config.get(key, default)

# Step 4: NotificationService remains unchanged!
# It automatically picks up the new @injectable versions
# No modifications needed whatsoever

# Step 5: Update main.py to use ConfigService
# main_v3.py
from fastapi import FastAPI, Depends
from services.config_service import ConfigService
from services.notification_service import NotificationService

app = FastAPI()

@app.get("/config")
async def get_config(config: ConfigService = Depends(ConfigService)):
    return {"db_path": config.get("db_path")}

@app.post("/notify/{user_id}")
async def notify_user(user_id: int, notifier: NotificationService = Depends(NotificationService)):
    success = notifier.notify_user(user_id, "Welcome to our service!")
    return {"notified": success, "user_id": user_id}

# Benefits:
# 1. Legacy classes now have proper lifecycle management
# 2. Configuration is centralized
# 3. Full scope safety
# 4. Still zero breaking changes to existing code
```

## Migration Strategies by Pattern

### Pattern 1: Global Instances → Singleton Services

**Before:**
```python
# Global instance (anti-pattern)
db = Database()

@app.get("/users")
def get_users():
    return db.query("SELECT * FROM users")
```

**During Migration (Phase 2):**
```python
# Keep global for legacy, but also allow injection
db = Database()

@injectable
class UserService:
    def __init__(self, database: Database = None):  # Optional, uses global fallback
        self.db = database or db
    
    def get_users(self):
        return self.db.query("SELECT * FROM users")

@app.get("/users")
def get_users(service: UserService = Depends(UserService)):
    return service.get_users()
```

**After (Phase 3):**
```python
# Remove global, use proper DI
@injectable(scope=Scopes.SINGLETON)
class Database:
    def __init__(self, config: ConfigService):
        self.config = config
    
    def query(self, sql: str):
        # Implementation
        pass

@injectable
class UserService:
    def __init__(self, db: Database):
        self.db = db
    
    def get_users(self):
        return self.db.query("SELECT * FROM users")

@app.get("/users")
def get_users(service: UserService = Depends(UserService)):
    return service.get_users()
```

### Pattern 2: Direct Instantiation → Injected Dependencies

**Before:**
```python
class ReportService:
    def generate_report(self, user_id: int):
        # Direct instantiation - hard to mock
        db = Database()
        user = db.get_user(user_id)
        email = EmailSender()
        email.send(user.email, "Report", "Your report is ready")
        return {"status": "sent"}
```

**During Migration (Phase 2):**
```python
@injectable
class ReportService:
    def __init__(self, db: Database = None, email: EmailSender = None):
        # Allow injection but provide defaults for legacy code
        self.db = db or Database()
        self.email = email or EmailSender()
    
    def generate_report(self, user_id: int):
        user = self.db.get_user(user_id)
        self.email.send(user["email"], "Report", "Your report is ready")
        return {"status": "sent"}

# Legacy code continues to work
legacy_service = ReportService()  # Uses default instances

# New code uses DI
@app.post("/reports/{user_id}")
def generate_report(user_id: int, service: ReportService = Depends(ReportService)):
    return service.generate_report(user_id)
```

**After (Phase 3):**
```python
@injectable
class ReportService:
    def __init__(self, db: Database, email: EmailSender):
        # No defaults - pure DI
        self.db = db
        self.email = email
    
    def generate_report(self, user_id: int):
        user = self.db.get_user(user_id)
        self.email.send(user["email"], "Report", "Your report is ready")
        return {"status": "sent"}

# Only DI usage now
@app.post("/reports/{user_id}")
def generate_report(user_id: int, service: ReportService = Depends(ReportService)):
    return service.generate_report(user_id)
```

### Pattern 3: Factory Functions → @injectable Classes

**Before:**
```python
def get_database():
    return Database("./app.db")

def get_user_service():
    db = get_database()
    return UserService(db)

@app.get("/users")
def get_users(service: UserService = Depends(get_user_service)):
    return service.get_users()
```

**After:**
```python
@injectable(scope=Scopes.SINGLETON)
class Database:
    def __init__(self, config: ConfigService):
        self.config = config

@injectable
class UserService:
    def __init__(self, db: Database):
        self.db = db

@app.get("/users")
def get_users(service: UserService = Depends(UserService)):
    # No factory functions needed!
    return service.get_users()
```

## Testing During Migration

### Test Strategy for Each Phase

**Phase 1 Tests (Legacy):**
```python
def test_legacy_direct():
    db = Database()
    email = EmailSender()
    user = db.get_user(1)
    assert user is not None
```

**Phase 2 Tests (Hybrid):**
```python
# Test new @injectable service with mocked legacy
def test_notification_with_mocks(container):
    container._registry[Database] = MockDatabase()
    container._registry[EmailSender] = MockEmailSender()
    
    service = container.resolve(NotificationService)
    result = service.notify_user(1, "Test")
    assert result is True
```

**Phase 3 Tests (Fully Modern):**
```python
# Test fully decorated stack
def test_complete_modern(container):
    # All services are @injectable
    service = container.resolve(UserService)
    user = service.get_user(1)
    assert user["id"] == 1
```

### Regression Testing

Ensure legacy code paths still work during migration:

```python
def test_backward_compatibility():
    # Old way still works
    legacy_db = Database()
    legacy_db.get_user(1)
    
    # New way also works
    from fastapi_service import Container
    container = Container()
    modern_db = container.resolve(Database)
    modern_db.get_user(1)
    
    # Both should produce same results
```

## Common Migration Pitfalls

### Pitfall 1: Scope Leaks During Transition

```python
# ❌ Dangerous intermediate state
@injectable(scope=Scopes.SINGLETON)  # New singleton
class NewService:
    def __init__(self, legacy: PlainLegacy):  # Plain legacy is transient
        self.legacy = legacy  # Scope leak!

# Solution: Transition both to singleton or both to transient
@injectable(scope=Scopes.TRANSIENT)  # Match scopes during transition
class NewService:
    def __init__(self, legacy: PlainLegacy):
        self.legacy = legacy
```

### Pitfall 2: Breaking Legacy Code

```python
# ❌ Breaking change
@injectable
class Database:
    def __init__(self, config: ConfigService):  # Now requires ConfigService
        self.config = config
    
    # Old code: Database() - now breaks!

# Solution: Maintain backward compatibility
class Database:
    def __init__(self, config: ConfigService = None):
        self.config = config or DefaultConfig()
    
    # Old: Database() - still works
    # New: Database(config) - also works
```

### Pitfall 3: Test Isolation Issues

```python
# ❌ Shared state between tests
@injectable(scope=Scopes.SINGLETON)
class CacheService:
    def __init__(self):
        self.data = {}  # Shared across tests

# Solution: Clear container between tests
@pytest.fixture
def container():
    c = Container()
    yield c
    c.clear()  # Ensures clean state
```

## Monitoring Migration Progress

Track your migration with metrics:

```python
# migration_metrics.py
from fastapi_service import injectable
import inspect

def count_injectable_classes(module):
    return len([
        obj for name, obj in inspect.getmembers(module)
        if inspect.isclass(obj) and hasattr(obj, '__injectable_metadata__')
    ])

def count_plain_classes(module):
    return len([
        obj for name, obj in inspect.getmembers(module)
        if inspect.isclass(obj) and not hasattr(obj, '__injectable_metadata__')
    ])

# Usage
import legacy_module
import modern_module

legacy_count = count_plain_classes(legacy_module)
modern_count = count_injectable_classes(modern_module)

print(f"Migration: {modern_count} / {legacy_count + modern_count} classes modernized")
```

## Final Migration Checklist

- [ ] All new services use `@injectable`
- [ ] Legacy services wrapped with `@injectable` adapters
- [ ] No global instances remain
- [ ] All dependencies use constructor injection
- [ ] Scope annotations are correct (SINGLETON for stateless, TRANSIENT for request-scoped)
- [ ] No scope leaks (singletons don't hold transients)
- [ ] Tests use `Container` for dependency overrides
- [ ] Configuration centralized in `ConfigService`
- [ ] Documentation updated
- [ ] Performance benchmarks show acceptable overhead (< 5%)

## Summary

Migration path:
1. **Phase 1**: Legacy code with global state
2. **Phase 2**: Hybrid - new code uses `@injectable`, depends on legacy via Plain Object Injection
3. **Phase 3**: Full modernization - all services use `@injectable`

**Key benefit**: Zero breaking changes at each phase. Your application continues to work while you modernize incrementally.

---

**Next: [Advanced Usage → Integrating with FastAPI Depends](../advanced/fastapi-integration.md)**
