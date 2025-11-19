from fastapi_service import injectable, Scopes


def test_injectable_basic_resolution(container):
    @injectable
    class SimpleService:
        def __init__(self):
            self.name = "SimpleService"

    instance = container.resolve(SimpleService)
    assert instance.name == "SimpleService"


def test_injectable_nested_dependencies(container):
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

    instance = container.resolve(Level3)
    assert instance.level == 3
    assert instance.dep.level == 2
    assert instance.dep.dep.level == 1


def test_scopes_singleton_transient(container):
    @injectable(scope=Scopes.SINGLETON)
    class SingletonService:
        def __init__(self):
            self.id = id(self)

    @injectable
    class NonSingletonService:
        def __init__(self):
            self.id = id(self)

    s1 = container.resolve(SingletonService)
    s2 = container.resolve(SingletonService)
    assert s1 is s2
    assert s1.id == s2.id

    n1 = container.resolve(NonSingletonService)
    n2 = container.resolve(NonSingletonService)
    assert n1 is not n2
    assert n1.id != n2.id


def test_edge_custom_new_instance(container):
    @injectable
    class FactoryService:
        def __new__(cls):
            return {"factory": True}

    result = container.resolve(FactoryService)
    assert isinstance(result, dict)
    assert result["factory"] is True


def test_singleton_cannot_depend_on_transient(container):
    @injectable
    class TransientService:
        def __init__(self):
            self.id = id(self)

    @injectable(scope=Scopes.SINGLETON)
    class SingletonService:
        def __init__(self, transient: TransientService):
            self.transient = transient

    try:
        container.resolve(SingletonService)
        assert False
    except ValueError as e:
        assert "Cannot inject non-singleton-scoped" in str(e)


def test_noop():
    assert True