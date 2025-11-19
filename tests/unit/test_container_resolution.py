from fastapi_service import injectable
from fastapi_service.injectable import _InjectableMetadata
from fastapi_service.enums import Scopes


def test_container_auto_resolve_unregistered_class(container):
    class Plain:
        def __init__(self):
            self.v = 1

    instance = container.resolve(Plain)
    assert instance.v == 1


def test_container_circular_dependency_detection(container):
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
        assert False
    except ValueError as e:
        assert "Circular dependency" in str(e)


def test_container_auto_resolve_function_call(container):
    @injectable
    class Data:
        def __init__(self):
            self.value = 42

    def factory(d: Data) -> int:
        return d.value

    result = container.resolve(factory)
    assert result == 42


def test_container_clear_resets_state(container):
    @injectable
    class X:
        def __init__(self):
            self.id = id(self)

    first = container.resolve(X)
    container.clear()
    second = container.resolve(X)
    assert first is not second
