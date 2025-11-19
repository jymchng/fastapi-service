from typing import (
    Any,
    Callable,
    Dict,
    Type,
    get_type_hints,
    Optional,
    overload,
    Union,
)
import inspect
import asyncio

from fastapi_service.enums import Scopes
from fastapi_service.helpers import (
    _get_injectable_metadata,
    get_solved_dependencies,
)
from fastapi_service.protocols import (
    ContainerProtocol,
)
from fastapi_service.constants import (
    FASTAPI_REQUEST_KEY,
)
from fastapi_service.typing import (
    _T,
    _TInjectable,
)
from fastapi_service.container import (
    Container,
)


class _InjectableMetadata:
    """Metadata attached to injectable classes."""

    def __init__(
        self,
        cls: Type,
        scope: Scopes = Scopes.TRANSIENT,
        dependencies: Optional[Dict[str, Type]] = None,
        original_init: Optional[Callable] = None,
        original_new: Optional[Callable] = None,
    ):
        self.cls = cls
        self.scope = scope
        self.dependencies = dependencies or {}
        self.original_init = original_init or object.__new__
        self.original_new = original_new or object.__new__
        self._instance: Optional[Any] = None

    def _dep_is_not_singleton_scope(self, dep_type: Type[_T]) -> None:
        """Check if a dependency is registered as singleton scope."""
        metadata = _get_injectable_metadata(dep_type) or False
        return not metadata or metadata.scope is not Scopes.SINGLETON

    def get_instance(
        self, container: "ContainerProtocol", additional_context: Dict[str, Any] = {}
    ) -> Any:
        """
        Get instance (singleton or new).
        Args:
            container: The container used to resolve dependencies
        Returns:
            An instance of the class, either cached (singleton) or newly created
        """
        if self.scope is Scopes.SINGLETON:
            if self._instance is None:
                self._instance = self._create_instance(container, additional_context)
            return self._instance
        return self._create_instance(container, additional_context)

    def _create_instance(
        self, container: "ContainerProtocol", additional_context: Dict[str, Any] = {}
    ) -> Any:
        """
        Create new instance with resolved dependencies.
        Args:
            container: The container used to resolve dependencies
        Returns:
            A new instance with all dependencies resolved and injected
        """
        resolved_deps = {}
        req = additional_context.get(FASTAPI_REQUEST_KEY)
        if self.original_new is not object.__new__:
            for param_name, dep_type in self.dependencies.items():
                if self.scope is Scopes.SINGLETON and self._dep_is_not_singleton_scope(
                    dep_type
                ):
                    raise ValueError(
                        f"Cannot inject non-singleton-scoped dependency '{dep_type.__name__}' "
                        f"into singleton-scoped '{self.cls.__name__}'"
                    )
                if req is not None:
                    additional_context = asyncio.run(
                        get_solved_dependencies(req, dep_type, {})
                    ).values
                    additional_context[FASTAPI_REQUEST_KEY] = req
                resolved_deps[param_name] = container.resolve(
                    dep_type, additional_context
                )

            instance = self.original_new(self.cls, **(resolved_deps))
        else:
            instance = self.original_new(self.cls)

        if not isinstance(instance, self.cls):
            return instance

        if self.original_init is not object.__init__:
            resolved_deps = {}
            for param_name, dep_type in self.dependencies.items():
                if self.scope is Scopes.SINGLETON and self._dep_is_not_singleton_scope(
                    dep_type
                ):
                    raise ValueError(
                        f"Cannot inject non-singleton-scoped dependency '{dep_type.__name__}' "
                        f"into singleton-scoped '{self.cls.__name__}'"
                    )
                if req is not None:
                    additional_context = asyncio.run(
                        get_solved_dependencies(req, dep_type, {})
                    ).values
                    additional_context[FASTAPI_REQUEST_KEY] = req
                resolved_deps[param_name] = container.resolve(
                    dep_type, additional_context
                )
            self.original_init(instance, **resolved_deps)
        else:
            self.original_init(instance)

        return instance


@overload
def injectable(
    _cls: Type[_T],
    *,
    scope: Scopes,
) -> Type[_TInjectable[_T]]: ...


@overload
def injectable(
    _cls: None,
    *,
    scope: Scopes,
) -> Callable[[Type[_T]], Type[_TInjectable[_T]]]: ...


def injectable(
    _cls: Optional[Type[_T]] = None,
    *,
    scope: Scopes = Scopes.TRANSIENT,
) -> Union[Callable[[Type[_T]], Type[_TInjectable[_T]]], Type[_TInjectable[_T]]]:
    """
    Decorator to mark a class as injectable.
    Args:
        scope: If Scopes.SINGLETON, only one instance will be created (default: Scopes.TRANSIENT)
    Usage:
        @injectable
        class MyService:
            pass
        @injectable(scope=Scopes.SINGLETON)
        class DatabaseService:
            pass
        @injectable
        class AuthService:
            def __init__(self, db: DatabaseService):
                self.db = db
    """
    if _cls is None:
        return lambda cls: injectable(cls, scope=scope)

    if hasattr(_cls, "__init__"):
        init_signature = inspect.signature(_cls.__init__)
        type_hints = get_type_hints(_cls.__init__)

        dependencies = {}
        for param_name, _ in init_signature.parameters.items():
            if param_name == "self":
                continue
            if param_name in type_hints:
                dependencies[param_name] = type_hints[param_name]

        original_init = _cls.__init__
        original_new = _cls.__new__ if hasattr(_cls, "__new__") else object.__new__

        metadata = _InjectableMetadata(
            cls=_cls,
            scope=scope,
            dependencies=dependencies,
            original_init=original_init,
            original_new=original_new,
        )

        _cls.__injectable_metadata__ = metadata

    return _cls


def Inject(
    dependency: Type[_TInjectable[_T]],
    *,
    use_cache: bool = True,
    container: Optional[ContainerProtocol] = None,
) -> _T:
    """
    Convenience wrapper for FastAPI's Depends.
    Usage:
        @app.get('/users')
        def get_users(auth: AuthService = Inject(AuthService)):
            ...
    """
    from fastapi import Depends, Request

    container = Container() if not container else container

    def factory(__fastapi_request__: Request):
        return container.resolve(dependency, {FASTAPI_REQUEST_KEY: __fastapi_request__})

    dependant = Depends(factory, use_cache=use_cache)
    return dependant


def Depends(
    dependency: Type[_TInjectable[_T]],
    *,
    use_cache: bool = True,
    container: Optional[ContainerProtocol] = None,
) -> _T:
    return Inject(dependency, use_cache=use_cache, container=container)
