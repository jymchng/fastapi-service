import pytest

from fastapi import FastAPI, Request, Depends, Path
from fastapi.testclient import TestClient
from fastapi_service import Scopes, Container, injectable
from fastapi_service.injectable import _InjectableMetadata


@injectable(scope=Scopes.SINGLETON)
class DatabaseService:
    def get_connection(self):
        return "db_connection"


@injectable
class CacheService:
    def get(self, key: str):
        return f"cached_{key}"


@injectable
class AuthService:
    def __init__(self, db: DatabaseService, cache: CacheService, should_auth=True):
        self.db = db
        self.cache = cache
        self.should_auth = should_auth

    def authenticate(self, user: str):
        conn = self.db.get_connection()
        cached = self.cache.get(user)
        return f"Authenticated {user} via {conn}, cache: {cached}"


@injectable
class UserService:
    def __init__(self, auth: AuthService, db: DatabaseService):
        self.auth = auth
        self.db = db

    def get_user(self, username: str):
        auth_result = self.auth.authenticate(username)
        return f"User {username}, {auth_result}"


def test_basic_dependency_resolution():
    """Test basic dependency resolution."""

    container = Container()

    @injectable
    class SimpleService:
        def __init__(self):
            self.name = "SimpleService"

    instance = container.resolve(SimpleService)
    assert instance.name == "SimpleService"


def test_nested_dependencies():
    """Test nested dependency resolution."""

    @injectable
    class Level1:
        def __init__(self):
            self.level = 1

    @injectable
    class Level2:
        def __init__(self, svc: Level1):
            self.level = 2
            self.dep = svc

    @injectable
    class Level3:
        def __init__(self, svc: Level2):
            self.level = 3
            self.dep = svc

    container = Container()
    instance = container.resolve(Level3)
    assert instance.level == 3
    assert instance.dep.level == 2
    assert instance.dep.dep.level == 1


def test_singleton_pattern():
    """Test singleton pattern."""

    @injectable(scope=Scopes.SINGLETON)
    class SingletonService:
        def __init__(self):
            self.id = id(self)

    @injectable
    class NonSingletonService:
        def __init__(self):
            self.id = id(self)

    container = Container()
    s1 = container.resolve(SingletonService)
    s2 = container.resolve(SingletonService)
    assert s1 is s2
    assert s1.id == s2.id

    n1 = container.resolve(NonSingletonService)
    n2 = container.resolve(NonSingletonService)
    assert n1 is not n2
    assert n1.id != n2.id


def test_multiple_dependencies():
    """Test class with multiple dependencies."""

    @injectable
    class ServiceA:
        def get_name(self):
            return "A"

    @injectable
    class ServiceB:
        def get_name(self):
            return "B"

    @injectable
    class ServiceC:
        def get_name(self):
            return "C"

    @injectable
    class MultiDepService:
        def __init__(self, a: ServiceA, b: ServiceB, c: ServiceC):
            self.a = a
            self.b = b
            self.c = c

        def get_all_names(self):
            return f"{self.a.get_name()}-{self.b.get_name()}-{self.c.get_name()}"

    container = Container()
    instance = container.resolve(MultiDepService)
    assert instance.get_all_names() == "A-B-C"


def test_singleton_in_dependency_chain():
    """Test singleton behavior in dependency chain."""

    @injectable(scope=Scopes.SINGLETON)
    class SharedDatabase:
        def __init__(self):
            self.connection_id = id(self)

    @injectable
    class Service1:
        def __init__(self, db: SharedDatabase):
            self.db = db

    @injectable
    class Service2:
        def __init__(self, db: SharedDatabase):
            self.db = db

    container = Container()
    s1 = container.resolve(Service1)
    s2 = container.resolve(Service2)

    assert s1.db is s2.db
    assert s1.db.connection_id == s2.db.connection_id


def test_complex_dependency_tree():
    """Test the example UserService dependency tree."""

    @injectable(scope=Scopes.SINGLETON)
    class Database:
        def __init__(self):
            self.id = id(self)

    @injectable
    class Cache:
        def __init__(self):
            self.id = id(self)

    @injectable
    class Auth:
        def __init__(self, db: Database, cache: Cache):
            self.db = db
            self.cache = cache

    @injectable
    class Users:
        def __init__(self, auth: Auth, db: Database):
            self.auth = auth
            self.db = db

    container = Container()
    user_service = container.resolve(Users)

    assert user_service.db is user_service.auth.db
    assert user_service.db.id == user_service.auth.db.id


def test_fastapi_integration():
    """Test FastAPI Depends integration."""
    from fastapi import Path

    def get_db_connection() -> "DBConnection":
        return DBConnection()

    class RequestScopedInjectable:
        def __init__(
            self,
            req: Request,
            name: str = Path(),
            db_connection=Depends(get_db_connection),
        ):
            self.req = req
            self.name = name
            self.db_connection = db_connection

    class DBConnection:
        def connect(self):
            return "db_connection"

    @injectable(scope=Scopes.SINGLETON)
    class ConfigService:
        def __init__(self, db_connection: DBConnection = Depends(get_db_connection)):
            self.db_connection = db_connection
            self.app_name = "TestApp"

    @injectable
    class GreetingService:
        def __init__(
            self,
            config: ConfigService,
            request_scoped_injectable: RequestScopedInjectable,
            db_connection: DBConnection = Depends(get_db_connection),
        ):
            self.config = config
            self.db_connection = db_connection
            self.request_scoped_injectable = request_scoped_injectable

        def greet(self, name: str):
            return f"Hello {name} from {self.config.app_name}"

    app = FastAPI()

    @app.get("/greet/{name}")
    def greet_user(
        name: str, greeting_service: GreetingService = Depends(GreetingService)
    ):
        return {"message": greeting_service.greet(name)}

    @app.get("/greet-direct/{name}")
    def greet_user_direct(
        name: str,
        greeting_service: GreetingService = Depends(GreetingService),
    ):
        return {"message": greeting_service.greet(name)}

    client = TestClient(app)

    # TODO: need to improve this such that `get_db_connection` can be resolved or at least marked as singleton scope
    with pytest.raises(ValueError) as exc_info:
        response = client.get("/greet/John")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        assert response.json() == {"message": "Hello John from TestApp"}

        response = client.get("/greet-direct/Jane")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        assert response.json() == {"message": "Hello Jane from TestApp"}

    assert (
        "Parameter with name `config` and type hint `ConfigService`cannot be resolved due to: Cannot inject non-singleton-scoped dependency 'db_connection' into singleton-scoped 'ConfigService'"
        in str(exc_info)
    )


def test_container_clear():
    """Test  functionality."""
    container = Container()

    @injectable(scope=Scopes.SINGLETON)
    class TestService:
        def __init__(self):
            self.id = id(self)

    s1 = container.resolve(TestService)

    @injectable(scope=Scopes.SINGLETON)
    class TestService:  # noqa: F811
        def __init__(self):
            self.id = id(self)

    s2 = container.resolve(TestService)

    assert s1.id != s2.id


def test_error_handling():
    """Test error handling for unregistered dependencies."""
    container = Container()

    class UnregisteredService:
        pass

    container.resolve(UnregisteredService)


def test_circular_dependency_detection():
    """Test circular dependency detection."""
    container = Container()

    class ServiceA:
        def __init__(self, b):
            self.b = b

    class ServiceB:
        def __init__(self, a):
            self.a = a

    metadata_a = _InjectableMetadata(
        cls=ServiceA, scope=Scopes.SINGLETON, dependencies={"b": ServiceB}
    )

    metadata_b = _InjectableMetadata(
        cls=ServiceB, scope=Scopes.SINGLETON, dependencies={"a": ServiceA}
    )

    ServiceA.__injectable_metadata__ = metadata_a
    ServiceB.__injectable_metadata__ = metadata_b
    metadata_a.original_init = ServiceA.__init__
    metadata_b.original_init = ServiceB.__init__

    container._registry[ServiceA] = metadata_a
    container._registry[ServiceB] = metadata_b

    try:
        container.resolve(ServiceA)
        assert False, "Should have raised ValueError for circular dependency"
    except ValueError as e:
        assert "Circular dependency detected" in str(e)


def test_fastapi_multiple_routes_same_service():
    """Test multiple routes using same service."""

    @injectable(scope=Scopes.SINGLETON)
    class CounterService:
        def __init__(self):
            self.count = 0

        def increment(self):
            self.count += 1
            return self.count

    app = FastAPI()

    @app.get("/count1")
    def route1(svc: CounterService = Depends(CounterService)):
        return {"count": svc.increment()}

    @app.get("/count2")
    def route2(svc: CounterService = Depends(CounterService)):
        return {"count": svc.increment()}

    client = TestClient(app)
    assert client.get("/count1").json() == {"count": 1}
    assert client.get("/count2").json() == {"count": 2}


def test_fastapi_path_parameters():
    """Test with path parameters."""

    @injectable
    class UserService:
        def get_user(self, user_id: int):
            return f"User{user_id}"

    app = FastAPI()

    @app.get("/users/{user_id}")
    def get_user(user_id: int, svc: UserService = Depends(UserService)):
        return {"user": svc.get_user(user_id)}

    client = TestClient(app)
    assert client.get("/users/123").json() == {"user": "User123"}


def test_fastapi_query_parameters():
    """Test with query parameters."""

    @injectable
    class SearchService:
        def search(self, query: str):
            return [f"Result for {query}"]

    app = FastAPI()

    @app.get("/search")
    def search(q: str, svc=Depends(SearchService)):
        return {"results": svc.search(q)}

    client = TestClient(app)
    assert client.get("/search?q=test").json() == {"results": ["Result for test"]}


def test_fastapi_post_with_body():
    """Test POST with request body."""

    from pydantic import BaseModel

    class CreateUser(BaseModel):
        name: str
        email: str

    @injectable
    class UserCreationService:
        def create(self, name: str, email: str):
            return {"id": 1, "name": name, "email": email}

    app = FastAPI()

    @app.post("/users")
    def create_user(
        user: CreateUser,
        svc: UserCreationService = Depends(UserCreationService),
    ):
        return svc.create(user.name, user.email)

    client = TestClient(app)
    response = client.post("/users", json={"name": "John", "email": "john@example.com"})
    assert response.json()["name"] == "John"


def test_fastapi_multiple_dependencies_per_route():
    """Test route with multiple injected dependencies."""

    @injectable
    class ServiceA:
        def get_a(self):
            return "A"

    @injectable
    class ServiceB:
        def get_b(self):
            return "B"

    app = FastAPI()

    @app.get("/combined")
    def combined(a: ServiceA = Depends(ServiceA), b: ServiceB = Depends(ServiceB)):
        return {"a": a.get_a(), "b": b.get_b()}

    client = TestClient(app)
    assert client.get("/combined").json() == {"a": "A", "b": "B"}


def test_fastapi_nested_dependencies():
    """Test nested dependency injection in routes."""

    @injectable
    class DbService:
        def query(self):
            return "data"

    @injectable
    class CacheService:
        def __init__(self, db: DbService):
            self.db = db

        def get_cached(self):
            return f"cached:{self.db.query()}"

    app = FastAPI()

    @app.get("/data")
    def get_data(cache: CacheService = Depends(CacheService)):
        return {"data": cache.get_cached()}

    client = TestClient(app)
    assert client.get("/data").json() == {"data": "cached:data"}


def test_fastapi_async_route():
    """Test async route with dependencies."""

    @injectable
    class AsyncService:
        async def process(self):
            return "processed"

    app = FastAPI()

    @app.get("/async")
    async def async_route(svc: AsyncService = Depends(AsyncService)):
        result = await svc.process()
        return {"result": result}

    client = TestClient(app)
    assert client.get("/async").json() == {"result": "processed"}


def test_fastapi_response_status():
    """Test custom response status codes."""
    from fastapi import status

    @injectable
    class CreationService:
        def create(self):
            return {"id": 1}

    app = FastAPI()

    @app.post("/items", status_code=status.HTTP_201_CREATED)
    def create_item(svc: CreationService = Depends(CreationService)):
        return svc.create()

    client = TestClient(app)
    response = client.post("/items")
    assert response.status_code == 201


def test_fastapi_exception_handling():
    """Test exception handling with DI."""
    from fastapi import HTTPException

    @injectable
    class ValidationService:
        def validate(self, value: int):
            if value < 0:
                raise HTTPException(status_code=400, detail="Invalid value")
            return value

    app = FastAPI()

    @app.get("/validate/{value}")
    def validate(value: int, svc: ValidationService = Depends(ValidationService)):
        return {"validated": svc.validate(value)}

    client = TestClient(app)
    assert client.get("/validate/10").status_code == 200
    assert client.get("/validate/-1").status_code == 400


def test_fastapi_header_dependencies():
    """Test with header parameters."""
    from fastapi import Header

    @injectable
    class AuthService:
        def verify_token(self, token: str):
            return token == "valid"

    app = FastAPI()

    @app.get("/protected")
    def protected(
        authorization: str = Header(...),
        auth: AuthService = Depends(AuthService),
    ):
        if not auth.verify_token(authorization):
            return {"error": "Unauthorized"}
        return {"message": "Authorized"}

    client = TestClient(app)
    response = client.get("/protected", headers={"authorization": "valid"})
    assert response.json() == {"message": "Authorized"}


def run_http_methods_tests():
    @injectable
    class CrudService:
        def __init__(self):
            self.items = {}
            self.next_id = 1

        def create(self, name: str):
            item_id = self.next_id
            self.items[item_id] = name
            self.next_id += 1
            return {"id": item_id, "name": name}

        def read(self, item_id: int):
            return {
                "id": item_id,
                "name": self.items.get(item_id, "Not found"),
            }

        def update(self, item_id: int, name: str):
            self.items[item_id] = name
            return {"id": item_id, "name": name}

        def delete(self, item_id: int):
            self.items.pop(item_id, None)
            return {"deleted": item_id}

    app = FastAPI()

    @app.post("/items")
    def create(name: str, svc: CrudService = Depends(CrudService)):
        return svc.create(name)

    @app.get("/items/{item_id}")
    def read(item_id: int, svc: CrudService = Depends(CrudService)):
        return svc.read(item_id)

    @app.put("/items/{item_id}")
    def update(item_id: int, name: str, svc: CrudService = Depends(CrudService)):
        return svc.update(item_id, name)

    @app.delete("/items/{item_id}")
    def delete(item_id: int, svc: CrudService = Depends(CrudService)):
        return svc.delete(item_id)

    client = TestClient(app)

    response = client.post("/items?name=Item1")
    assert response.json()["name"] == "Item1"

    response = client.get("/items/1")
    assert response.status_code == 200

    response = client.put("/items/1?name=UpdatedItem")
    assert response.json()["name"] == "UpdatedItem"

    response = client.delete("/items/1")
    assert response.json()["deleted"] == 1

    @app.patch("/items/{item_id}")
    def patch(item_id: int, svc: CrudService = Depends(CrudService)):
        return {"patched": item_id}

    response = client.patch("/items/1")
    assert response.json()["patched"] == 1


def test_run_advanced_patterns_tests():
    @injectable
    class ConnectionFactory:
        def create_connection(self, db_type: str):
            return f"Connection to {db_type}"

    app = FastAPI()

    @app.get("/connect/{db_type}")
    def connect(
        db_type: str,
        factory: ConnectionFactory = Depends(ConnectionFactory),
    ):
        return {"connection": factory.create_connection(db_type)}

    client = TestClient(app)
    assert "postgres" in client.get("/connect/postgres").json()["connection"]

    @injectable
    class UserRepository:
        def __init__(self):
            self.users = {"1": "Alice", "2": "Bob"}

        def find_by_id(self, user_id: str):
            return self.users.get(user_id)

    @app.get("/users/{user_id}")
    def get_user(user_id: str, repo: UserRepository = Depends(UserRepository)):
        return {"user": repo.find_by_id(user_id)}

    assert client.get("/users/1").json()["user"] == "Alice"

    @injectable
    class DataService:
        def get_data(self):
            return "raw_data"

    @injectable
    class BusinessService:
        def __init__(self, data: DataService):
            self.data = data

        def process(self):
            return self.data.get_data().upper()

    @app.get("/process")
    def process(biz: BusinessService = Depends(BusinessService)):
        return {"result": biz.process()}

    assert client.get("/process").json()["result"] == "RAW_DATA"


def test_run_error_scenarios_tests():
    from fastapi import HTTPException

    app = FastAPI()

    @injectable
    class ErrorService:
        def may_fail(self, should_fail: bool):
            if should_fail:
                raise HTTPException(status_code=500, detail="Service error")
            return "success"

    @app.get("/may-fail")
    def may_fail(fail: bool = False, svc: ErrorService = Depends(ErrorService)):
        return {"result": svc.may_fail(fail)}

    client = TestClient(app)
    assert client.get("/may-fail").status_code == 200
    assert client.get("/may-fail?fail=true").status_code == 500


def run_performance_tests():
    app = FastAPI()

    @injectable(scope=Scopes.SINGLETON)
    class ExpensiveService:
        def __init__(self):
            self.init_count = 0
            self.init_count += 1

    @app.get("/expensive1")
    def route1(svc: ExpensiveService = Depends(ExpensiveService)):
        return {"count": svc.init_count}

    @app.get("/expensive2")
    def route2(svc: ExpensiveService = Depends(ExpensiveService)):
        return {"count": svc.init_count}

    client = TestClient(app)
    assert client.get("/expensive1").json()["count"] == 1
    assert client.get("/expensive2").json()["count"] == 1

    @injectable
    class TransientService:
        def __init__(self):
            self.instance_id = id(self)

    @app.get("/transient")
    def transient(svc: TransientService = Depends(TransientService)):
        return {"id": svc.instance_id}

    id1 = client.get("/transient").json()["id"]
    id2 = client.get("/transient").json()["id"]
    assert id1 != id2


def test_singleton_injectable_cannot_depend_on_transient_injectable():
    """Test that a singleton injectable cannot depend on a transient injectable."""
    container = Container()
    TEST_NUMBER = 69

    @injectable
    class TransientService:
        def __init__(self, num=TEST_NUMBER):
            self.id = id(self)
            self.num = num

    @injectable(scope=Scopes.SINGLETON)
    class SingletonService:
        def __init__(self, transient=Depends(TransientService)):
            self.transient = transient

    # resolving without fastapi's Request
    svc = container.resolve(SingletonService)
    DependsType = type(Depends())
    assert isinstance(svc.transient, DependsType)

    app = FastAPI()

    # previous test failed because `SingletonService` is a singleton
    # `svc = container.resolve(SingletonService)` already previously solved
    # its dependency and made `svc.transient` to be of type `type(Depends())`
    # hence subsequent test fail with `AttributeError: 'Depends' object has no attribute 'id'`
    # so here we redefine `SingletonService`
    @injectable(scope=Scopes.SINGLETON)
    class SingletonService:
        def __init__(self, transient=Depends(TransientService)):
            self.transient = transient

    @app.get("/test")
    def test_route(svc: SingletonService = Depends(SingletonService)):
        return {"transient_id": svc.transient.id}

    testclient = TestClient(app)
    with pytest.raises(ValueError):
        testclient.get("/test")  # This should also raise the error


def test_can_still_instantiate_regularly():
    TEST_NUMBER = 69

    class TransientService:
        def __init__(self, num=Depends(lambda: TEST_NUMBER), num1=TEST_NUMBER):
            self.id = id(self)
            self.num = num
            self.num1 = num1

    @injectable
    class TransientServiceTwo:
        def __init__(self, transient: TransientService):
            self.transient = transient

    app = FastAPI()

    @app.get("/test")
    def test_route(svc=Depends(TransientServiceTwo)):
        return {
            "num": svc.transient.num,
            "num1": svc.transient.num1,
        }

    testclient = TestClient(app)
    assert testclient.get("/test").json() == {"num": TEST_NUMBER, "num1": TEST_NUMBER}

    transient_svc = TransientService(70)
    assert transient_svc.num == 70
    assert transient_svc.num1 == TEST_NUMBER
    transient_svc_two = TransientServiceTwo(transient_svc)

    assert transient_svc_two.transient.num == 70

    class ChildTransientService(TransientService):
        def __init__(self, num: int = 71, num1: int = 72):
            super().__init__(num)
            self.num1 = num1

    child_transient_svc = ChildTransientService(54, 55)
    assert child_transient_svc.num == 54
    assert child_transient_svc.num1 == 55

    @app.get("/test/{name}")
    def test_route(
        name: str, svc: ChildTransientService = Depends(ChildTransientService)
    ):
        return {
            "name": name,
            "num": svc.num,
            "num1": svc.num1,
        }

    assert testclient.get("/test/James").json() == {
        "name": "James",
        "num": 71,
        "num1": 72,
    }


def test_work_with_default_args():
    @injectable
    class Service:
        def __init__(self, num1=69, num2=70):
            self.num1 = num1
            self.num2 = num2

    container = Container()
    svc = container.resolve(Service)

    assert svc.num1 == 69
    assert svc.num2 == 70
