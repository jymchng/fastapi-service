import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from fastapi_service import injectable, Scopes


def test_subclass_of_singleton_is_transient_basic(container):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self):
            self.x = 1

    class Child(Base):
        pass

    a = container.resolve(Child)
    b = container.resolve(Child)
    assert a is not b


def test_subclass_of_transient_is_transient_basic(container):
    @injectable
    class Base:
        def __init__(self):
            self.x = 2

    class Child(Base):
        pass

    a = container.resolve(Child)
    b = container.resolve(Child)
    assert a is not b


def test_subclass_does_not_share_parent_singleton_instance(container):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self):
            self.id = id(self)

    class Child(Base):
        pass

    p1 = container.resolve(Base)
    c1 = container.resolve(Child)
    assert p1 is not c1


def test_subclass_autoresolve_dependency(container):
    @injectable
    class Dep:
        def __init__(self):
            self.v = 10

    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self, d: Dep):
            self.d = d

    class Child(Base):
        def __init__(self, d: Dep):
            super().__init__(d)

    obj = container.resolve(Child)
    assert obj.d.v == 10


def test_subclass_untyped_param_raises(container):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self, x: int):
            self.x = x

    class Child(Base):
        def __init__(self, x):
            super().__init__(x)

    with pytest.raises(ValueError):
        container.resolve(Child)


def test_subclass_default_param_uses_default(container):
    @injectable
    class Base:
        def __init__(self, x: int = 4):
            self.x = x

    class Child(Base):
        def __init__(self, x: int = 3):
            super().__init__(x)

    obj = container.resolve(Child)
    assert obj.x == 3


def test_subclass_multiple_resolves_distinct_ids(container):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self):
            self.id = id(self)

    class Child(Base):
        pass

    a = container.resolve(Child)
    b = container.resolve(Child)
    assert a.id != b.id


def test_subclass_chain_three_levels(container):
    @injectable
    class Dep:
        def __init__(self):
            self.v = 1

    @injectable(scope=Scopes.SINGLETON)
    class A:
        def __init__(self, d: Dep):
            self.d = d

    class B(A):
        def __init__(self, d: Dep):
            super().__init__(d)

    class C(B):
        def __init__(self, d: Dep):
            super().__init__(d)

    obj = container.resolve(C)
    assert obj.d.v == 1


def test_subclass_in_fastapi_depends_transient(app):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self):
            self.id = id(self)

    class Child(Base):
        pass

    @app.get("/id")
    def route(inst: Child = Depends(Child)):
        return {"id": id(inst)}

    client = TestClient(app)
    r1 = client.get("/id").json()["id"]
    r2 = client.get("/id").json()["id"]
    assert r1 != r2


def test_subclass_independent_of_parent_registry(container):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self):
            self.name = "base"

    class Child(Base):
        pass

    _ = container.resolve(Child)
    assert Child in container._registry


def test_subclass_autoresolve_function_param(container):
    @injectable
    class Dep:
        def __init__(self):
            self.v = 5

    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self, d: Dep):
            self.d = d

    class Child(Base):
        def __init__(self, d: Dep):
            super().__init__(d)

    def factory(x: Child) -> int:
        return x.d.v

    val = container.resolve(factory)
    assert val == 5


def test_subclass_custom_new_returns_dict(container):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self):
            pass

    class Child(Base):
        def __new__(cls):
            return {"k": 1}

    inst = container.resolve(Child)
    assert isinstance(inst, dict)


def test_subclass_transient_with_state(container):
    @injectable
    class Base:
        def __init__(self):
            self.counter = 0

    class Child(Base):
        def bump(self):
            self.counter += 1

    a = container.resolve(Child)
    b = container.resolve(Child)
    a.bump()
    assert a.counter == 1
    assert b.counter == 0


def test_subclass_of_singleton_not_cached(container):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self):
            self.t = id(self)

    class Child(Base):
        pass

    x = container.resolve(Child)
    y = container.resolve(Child)
    assert x is not y


def test_subclass_autoresolve_uses_container_for_dependencies(container):
    @injectable
    class Dep:
        def __init__(self):
            self.v = 99

    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self, d: Dep):
            self.d = d

    class Child(Base):
        def __init__(self, d: Dep):
            super().__init__(d)

    obj = container.resolve(Child)
    assert obj.d.v == 99


def test_subclass_with_default_and_dependency(container):
    @injectable
    class Dep:
        def __init__(self):
            self.v = 1

    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self, d: Dep, x: int = 7):
            self.d = d
            self.x = x

    class Child(Base):
        def __init__(self, d: Dep, x: int = 7):
            super().__init__(d, x)

    obj = container.resolve(Child)
    assert obj.x == 7


def test_subclass_function_default_skip(container):
    class Base:
        def __init__(self, a: int = 1):
            self.a = a

    Base = injectable(Base)

    class Child(Base):
        def __init__(self, a: int = 1):
            super().__init__(a)

    def f(x: Child = 0):
        return 0

    assert container.resolve(f) == 0


def test_subclass_circular_not_engaged(container):
    @injectable(scope=Scopes.SINGLETON)
    class A:
        def __init__(self):
            pass

    class B(A):
        def __init__(self, a: A):
            self.a = a

    obj = container.resolve(B)
    assert isinstance(obj.a, A)


def test_subclass_integration_multiple_calls(app):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self):
            self.id = id(self)

    class Child(Base):
        pass

    @app.get("/multi")
    def route(inst: Child = Depends(Child)):
        return {"id": id(inst)}

    client = TestClient(app)
    ids = {client.get("/multi").json()["id"] for _ in range(5)}
    assert len(ids) == 5


def test_subclass_with_extra_dependency(container):
    @injectable
    class DepA:
        def __init__(self):
            self.v = 1

    @injectable
    class DepB:
        def __init__(self):
            self.w = 2

    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self, a: DepA):
            self.a = a

    class Child(Base):
        def __init__(self, a: DepA, b: DepB):
            super().__init__(a)
            self.b = b

    obj = container.resolve(Child)
    assert obj.a.v == 1 and obj.b.w == 2


def test_subclass_dependency_default_values(container):
    @injectable
    class Dep:
        def __init__(self):
            self.v = 3

    @injectable(scope=Scopes.TRANSIENT)
    class Base:
        def __init__(self, d: Dep, k: int = 9):
            self.d = d
            self.k = k

    class Child(Base):
        def __init__(self, d: Dep, k: int = 9):
            super().__init__(d, k)

    obj = container.resolve(Child)
    assert obj.k == 9


def test_subclass_mutation_isolated(container):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self):
            self.state = []

    class Child(Base):
        def add(self, v):
            self.state.append(v)

    a = container.resolve(Child)
    b = container.resolve(Child)
    a.add(1)
    assert a.state == [1]
    assert b.state == []


def test_subclass_identity_differs_from_parent_instance(container):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self):
            pass

    class Child(Base):
        pass

    p = container.resolve(Base)
    c = container.resolve(Child)
    assert type(p) is not type(c)


def test_subclass_with_positional_and_kw(container):
    @injectable
    class Dep:
        def __init__(self):
            self.v = 7

    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self, d: Dep, *, x: int = 2):
            self.d = d
            self.x = x

    class Child(Base):
        def __init__(self, d: Dep, *, x: int = 2):
            super().__init__(d, x=x)

    obj = container.resolve(Child)
    assert obj.x == 2


def test_subclass_dependency_resolution_order(container):
    @injectable
    class A:
        def __init__(self):
            self.v = "a"

    @injectable
    class B:
        def __init__(self, a: A):
            self.a = a

    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self, b: B):
            self.b = b

    class Child(Base):
        def __init__(self, b: B):
            super().__init__(b)

    obj = container.resolve(Child)
    assert obj.b.a.v == "a"


def test_subclass_inheritance_does_not_change_scope(container):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self):
            self.id = id(self)

    class Child(Base):
        pass

    a = container.resolve(Child)
    b = container.resolve(Child)
    assert a.id != b.id


def test_subclass_resolve_after_parent_used(container):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self):
            self.id = id(self)

    class Child(Base):
        pass

    _ = container.resolve(Base)
    a = container.resolve(Child)
    b = container.resolve(Child)
    assert a is not b


def test_subclass_of_transient_with_dependency(container):
    @injectable
    class Dep:
        def __init__(self):
            self.v = 4

    @injectable
    class Base:
        def __init__(self, d: Dep):
            self.d = d

    class Child(Base):
        def __init__(self, d: Dep):
            super().__init__(d)

    a = container.resolve(Child)
    b = container.resolve(Child)
    assert a is not b and a.d.v == 4 and b.d.v == 4


def test_subclass_fastapi_query_params(app):
    @injectable
    class Base:
        def __init__(self):
            self.id = id(self)

    class Child(Base):
        pass

    @app.get("/q")
    def route(inst=Depends(Child), q: int = 1):
        return {"id": id(inst), "q": q}

    client = TestClient(app)
    a = client.get("/q?q=2").json()
    b = client.get("/q?q=3").json()
    assert a["id"] != b["id"] and a["q"] == 2 and b["q"] == 3


def test_subclass_with_inherited_attribute(container):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        attr = "z"

        def __init__(self):
            pass

    class Child(Base):
        pass

    obj = container.resolve(Child)
    assert obj.attr == "z"


def test_subclass_distinct_instances_ids(container):
    @injectable(scope=Scopes.SINGLETON)
    class Base:
        def __init__(self):
            pass

    class Child(Base):
        pass

    ids = [id(container.resolve(Child)) for _ in range(6)]
    assert len(set(ids)) == 6
