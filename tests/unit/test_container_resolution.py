import inspect
from fastapi_service import injectable


def test_container_auto_resolve_unregistered_class(container):
    class Plain:
        def __init__(self):
            self.v = 1

    instance = container.resolve(Plain)
    assert instance.v == 1


def test_container_circular_dependency_detection(container):
    @injectable
    class A:
        def __init__(self, b: "B"):
            self.b = b

    @injectable
    class B:
        def __init__(self, a: A):
            self.a = a

    try:
        container.resolve(A)
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