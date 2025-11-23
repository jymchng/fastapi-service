# Tutorial: Building a Complete Application

This tutorial walks you through building a complete FastAPI application with FastAPI Service, including database operations, authentication, and testing.

## Project Setup

Create a new project directory:

```bash
mkdir todo-app
cd todo-app
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install fastapi-service fastapi uvicorn
```

## Step 1: Define Your Data Models

```python
# models.py
from typing import Optional
from datetime import datetime

class TodoItem:
    def __init__(self, id: int, title: str, description: str, completed: bool = False):
        self.id = id
        self.title = title
        self.description = description
        self.completed = completed
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

class User:
    def __init__(self, id: int, username: str, email: str):
        self.id = id
        self.username = username
        self.email = email
```

## Step 2: Create Configuration Service

```python
# config.py
import os
from typing import Dict, Any
from fastapi_service import injectable, Scopes

@injectable(scope=Scopes.SINGLETON)
class ConfigService:
    def __init__(self):
        self._config = {
            "database_url": os.getenv("DATABASE_URL", "sqlite:///./todos.db"),
            "secret_key": os.getenv("SECRET_KEY", "your-secret-key"),
            "debug": os.getenv("DEBUG", "false").lower() == "true",
            "api_version": "v1"
        }
    
    def get(self, key: str, default=None) -> Any:
        return self._config.get(key, default)
    
    def get_database_url(self) -> str:
        return self.get("database_url")
```

## Step 3: Create Database Service

```python
# database.py
import sqlite3
from typing import List, Optional
from fastapi_service import injectable
from models import TodoItem, User

@injectable
class DatabaseService:
    def __init__(self, config: ConfigService):
        self.config = config
        self.connection_string = config.get_database_url()
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.connection_string) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    completed BOOLEAN DEFAULT 0,
                    user_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                )
            """)
    
    def create_todo(self, title: str, description: str, user_id: int) -> TodoItem:
        with sqlite3.connect(self.connection_string) as conn:
            cursor = conn.execute(
                "INSERT INTO todos (title, description, user_id) VALUES (?, ?, ?)",
                (title, description, user_id)
            )
            todo_id = cursor.lastrowid
            return self.get_todo_by_id(todo_id)
    
    def get_todo_by_id(self, todo_id: int) -> Optional[TodoItem]:
        with sqlite3.connect(self.connection_string) as conn:
            cursor = conn.execute(
                "SELECT id, title, description, completed, created_at, updated_at FROM todos WHERE id = ?",
                (todo_id,)
            )
            row = cursor.fetchone()
            if row:
                return TodoItem(
                    id=row[0],
                    title=row[1],
                    description=row[2],
                    completed=bool(row[3])
                )
            return None
    
    def get_todos_by_user(self, user_id: int) -> List[TodoItem]:
        with sqlite3.connect(self.connection_string) as conn:
            cursor = conn.execute(
                "SELECT id, title, description, completed, created_at, updated_at FROM todos WHERE user_id = ?",
                (user_id,)
            )
            todos = []
            for row in cursor.fetchall():
                todos.append(TodoItem(
                    id=row[0],
                    title=row[1],
                    description=row[2],
                    completed=bool(row[3])
                ))
            return todos
    
    def update_todo(self, todo_id: int, title: str, description: str, completed: bool) -> Optional[TodoItem]:
        with sqlite3.connect(self.connection_string) as conn:
            conn.execute(
                "UPDATE todos SET title = ?, description = ?, completed = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (title, description, completed, todo_id)
            )
            return self.get_todo_by_id(todo_id)
    
    def delete_todo(self, todo_id: int) -> bool:
        with sqlite3.connect(self.connection_string) as conn:
            cursor = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            return cursor.rowcount > 0
```

## Step 4: Create Authentication Service

```python
# auth.py
import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi_service import injectable
from models import User

@injectable
class AuthService:
    def __init__(self, config: ConfigService):
        self.config = config
        self.secret_key = config.get("secret_key")
    
    def create_access_token(self, user_id: int, username: str) -> str:
        expire = datetime.utcnow() + timedelta(hours=24)
        payload = {
            "sub": str(user_id),
            "username": username,
            "exp": expire
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")
    
    def verify_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
```

## Step 5: Create Business Logic Services

```python
# services.py
from typing import List, Optional
from fastapi_service import injectable
from models import TodoItem

@injectable
class TodoService:
    def __init__(self, db: DatabaseService):
        self.db = db
    
    def create_todo(self, title: str, description: str, user_id: int) -> TodoItem:
        return self.db.create_todo(title, description, user_id)
    
    def get_todo(self, todo_id: int, user_id: int) -> Optional[TodoItem]:
        todo = self.db.get_todo_by_id(todo_id)
        if todo and self._belongs_to_user(todo, user_id):
            return todo
        return None
    
    def get_user_todos(self, user_id: int) -> List[TodoItem]:
        return self.db.get_todos_by_user(user_id)
    
    def update_todo(self, todo_id: int, title: str, description: str, completed: bool, user_id: int) -> Optional[TodoItem]:
        if not self._todo_exists_and_belongs_to_user(todo_id, user_id):
            return None
        return self.db.update_todo(todo_id, title, description, completed)
    
    def delete_todo(self, todo_id: int, user_id: int) -> bool:
        if not self._todo_exists_and_belongs_to_user(todo_id, user_id):
            return False
        return self.db.delete_todo(todo_id)
    
    def _belongs_to_user(self, todo: TodoItem, user_id: int) -> bool:
        # In a real app, you'd store user_id with the todo
        # For this tutorial, we'll assume all todos belong to the user
        return True
    
    def _todo_exists_and_belongs_to_user(self, todo_id: int, user_id: int) -> bool:
        todo = self.db.get_todo_by_id(todo_id)
        return todo is not None and self._belongs_to_user(todo, user_id)

@injectable
class UserService:
    def __init__(self, db: DatabaseService):
        self.db = db
    
    def get_user_by_id(self, user_id: int):
        # Simplified for tutorial
        return {"id": user_id, "username": f"user_{user_id}"}
```

## Step 6: Create FastAPI Application

```python
# main.py
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi_service import injectable
from services import TodoService, UserService
from auth import AuthService
from models import TodoItem

app = FastAPI(title="Todo API", version="1.0.0")

def get_current_user(authorization: str = Header(None)) -> dict:
    """Extract user from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.split(" ")[1]
    auth_service = AuthService.__new__(AuthService)  # Simplified for tutorial
    payload = auth_service.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return payload

@app.post("/todos", response_model=dict)
async def create_todo(
    title: str,
    description: str,
    todo_service: TodoService = Depends(TodoService),
    current_user: dict = Depends(get_current_user)
):
    """Create a new todo item"""
    user_id = int(current_user["sub"])
    todo = todo_service.create_todo(title, description, user_id)
    return {"id": todo.id, "title": todo.title, "description": todo.description, "completed": todo.completed}

@app.get("/todos", response_model=list)
async def get_todos(
    todo_service: TodoService = Depends(TodoService),
    current_user: dict = Depends(get_current_user)
):
    """Get all todos for the current user"""
    user_id = int(current_user["sub"])
    todos = todo_service.get_user_todos(user_id)
    return [{"id": t.id, "title": t.title, "description": t.description, "completed": t.completed} for t in todos]

@app.get("/todos/{todo_id}", response_model=dict)
async def get_todo(
    todo_id: int,
    todo_service: TodoService = Depends(TodoService),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific todo item"""
    user_id = int(current_user["sub"])
    todo = todo_service.get_todo(todo_id, user_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"id": todo.id, "title": todo.title, "description": todo.description, "completed": todo.completed}

@app.put("/todos/{todo_id}", response_model=dict)
async def update_todo(
    todo_id: int,
    title: str,
    description: str,
    completed: bool,
    todo_service: TodoService = Depends(TodoService),
    current_user: dict = Depends(get_current_user)
):
    """Update a todo item"""
    user_id = int(current_user["sub"])
    todo = todo_service.update_todo(todo_id, title, description, completed, user_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"id": todo.id, "title": todo.title, "description": todo.description, "completed": todo.completed}

@app.delete("/todos/{todo_id}")
async def delete_todo(
    todo_id: int,
    todo_service: TodoService = Depends(TodoService),
    current_user: dict = Depends(get_current_user)
):
    """Delete a todo item"""
    user_id = int(current_user["sub"])
    success = todo_service.delete_todo(todo_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"message": "Todo deleted successfully"}

@app.get("/")
async def root():
    return {"message": "Todo API", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Step 7: Testing Your Application

```python
# test_main.py
import pytest
from fastapi.testclient import TestClient
from fastapi_service import Container
from main import app
from services import TodoService, DatabaseService
from config import ConfigService

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def container():
    c = Container()
    yield c
    c.clear()

def test_create_and_get_todo(client, container):
    # Mock the database service
    class MockDatabaseService:
        def create_todo(self, title, description, user_id):
            from models import TodoItem
            return TodoItem(id=1, title=title, description=description)
        
        def get_todo_by_id(self, todo_id):
            from models import TodoItem
            return TodoItem(id=todo_id, title="Test Todo", description="Test Description")
        
        def get_todos_by_user(self, user_id):
            return []
        
        def update_todo(self, todo_id, title, description, completed):
            from models import TodoItem
            return TodoItem(id=todo_id, title=title, description=description, completed=completed)
        
        def delete_todo(self, todo_id):
            return True
    
    # Register the mock
    container._registry[DatabaseService] = MockDatabaseService()
    
    # Create a mock auth token
    from auth import AuthService
    auth_service = AuthService(container.resolve(ConfigService))
    token = auth_service.create_access_token(1, "testuser")
    
    # Test creating a todo
    response = client.post(
        "/todos",
        params={"title": "Test Todo", "description": "Test Description"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Todo"
    assert data["description"] == "Test Description"
    
    # Test getting todos
    response = client.get("/todos", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    
    # Test getting specific todo
    response = client.get(f"/todos/{data['id']}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    
    # Test updating todo
    response = client.put(
        f"/todos/{data['id']}",
        params={"title": "Updated Todo", "description": "Updated Description", "completed": True},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    updated_data = response.json()
    assert updated_data["completed"] is True
    
    # Test deleting todo
    response = client.delete(f"/todos/{data['id']}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_unauthorized_access(client):
    response = client.get("/todos")
    assert response.status_code == 401
```

## Step 8: Running Your Application

```bash
# Run the application
python main.py

# Or with uvicorn
uvicorn main:app --reload

# Run tests
pytest test_main.py -v
```

## What You've Learned

In this tutorial, you built a complete FastAPI application with:

1. **Dependency Injection**: Services automatically resolve their dependencies
2. **Scope Management**: Configuration as singleton, database sessions as transient
3. **Authentication**: JWT-based authentication with dependency injection
4. **Testing**: Unit tests with dependency mocking
5. **Database Operations**: SQLite with proper connection management
6. **RESTful API**: Complete CRUD operations for todo items

## Next Steps

- [Advanced Usage](../advanced/fastapi-integration.md) - Learn integration patterns
- [API Reference](../reference/service.md) - Explore the complete API
- [Contributing](../../contributing.md) - Contribute to the project