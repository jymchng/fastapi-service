from typing import (
    Any,
    Callable,
    Dict,
    Type,
    get_type_hints,
    Optional,
)
from dataclasses import dataclass, field
import inspect
import asyncio

from fastapi_shield.enums import Scopes
from fastapi_shield.helpers import (
    _get_injectable_metadata,
    get_solved_dependencies,
    _is_injectable_instance,
)
from fastapi_shield.protocols import (
    ContainerProtocol,
)
from fastapi_shield.constants import (
    FASTAPI_REQUEST_KEY,
)
from fastapi_shield.typing import (
    _T,
    _TInjectable,
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

    def get_instance(self, container: "ContainerProtocol", additional_context: Dict[str, Any] = {}) -> Any:
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

    def _create_instance(self, container: "ContainerProtocol", additional_context: Dict[str, Any] = {}) -> Any:
        """
        Create new instance with resolved dependencies.
        Args:
            container: The container used to resolve dependencies
        Returns:
            A new instance with all dependencies resolved and injected
        """
        # Resolve dependencies using the container
        resolved_deps = {}
        req = additional_context.get(FASTAPI_REQUEST_KEY)
        if self.original_new is not object.__new__:

            for param_name, dep_type in self.dependencies.items():
                if self.scope is Scopes.SINGLETON and self._dep_is_not_singleton_scope(dep_type):
                    raise ValueError(
                        f"Cannot inject non-singleton-scoped dependency '{dep_type.__name__}' "
                        f"into singleton-scoped '{self.cls.__name__}'"
                    )
                if req is not None:
                    additional_context = asyncio.run(get_solved_dependencies(req, dep_type, {})).values
                    additional_context[FASTAPI_REQUEST_KEY] = req
                resolved_deps[param_name] = container.resolve(dep_type, additional_context)

            # Create instance using original __new__ (stored in metadata)
            instance = self.original_new(self.cls, **(resolved_deps))
        else:
            # Create instance using original __new__ (stored in metadata)
            instance = self.original_new(self.cls)

        if not isinstance(instance, self.cls):
            return instance

        # Call original __init__ with resolved dependencies
        if self.original_init is not object.__init__:
            resolved_deps = {}
            # need to resolve because `__new__` and `__init__` may have different dependencies
            for param_name, dep_type in self.dependencies.items():
                if self.scope is Scopes.SINGLETON and self._dep_is_not_singleton_scope(dep_type):
                    raise ValueError(
                        f"Cannot inject non-singleton-scoped dependency '{dep_type.__name__}' "
                        f"into singleton-scoped '{self.cls.__name__}'"
                    )
                if req is not None:
                    additional_context = asyncio.run(get_solved_dependencies(req, dep_type, {})).values
                    additional_context[FASTAPI_REQUEST_KEY] = req
                resolved_deps[param_name] = container.resolve(dep_type, additional_context)
            self.original_init(instance, **resolved_deps)
        else:
            self.original_init(instance)

        return instance


@dataclass
class Container:
    """Dependency injection container."""

    _registry: Dict[Type, _InjectableMetadata] = field(default_factory=dict)
    _instances: Dict[Type[_TInjectable[_T]], _T] = field(default_factory=dict)
    _resolving: set = field(
        default_factory=set
    )  # Track currently resolving dependencies

    def resolve(self, dependency: Type[_TInjectable[_T]], additional_context: Dict[str, Any]={}) -> _T:
        """
        Resolve a dependency by type.
        Compatible with FastAPI's Depends.
        Usage:
            @app.get('/users')
            def get_users(auth: AuthService = Depends(container.resolve)):
                ...
        """
        # Circular dependency detection
        if dependency in self._resolving:
            chain = " -> ".join([d.__name__ for d in self._resolving])
            raise ValueError(
                f"Circular dependency detected: {chain} -> {dependency.__name__}"
            )

        try:
            self._resolving.add(dependency)

            # Check if already registered
            if dependency in self._registry:
                metadata = self._registry[dependency]
                return metadata.get_instance(self, additional_context)

            # Check if the class has injectable metadata
            if _is_injectable_instance(dependency):
                metadata = dependency.__injectable_metadata__
                # subclass will inherit parent's metadata
                if metadata.cls is dependency:
                    self._registry[metadata.cls] = metadata
                    return metadata.get_instance(self, additional_context)

            # Try to auto-resolve if it has type-hinted __init__
            try:
               
                return self._auto_resolve(dependency, additional_context)
            except Exception as e:
                raise ValueError(
                    f"Cannot resolve dependency {dependency}. "
                    f"Make sure it's decorated with `@injectable`. Error: {e}"
                )
        finally:
            self._resolving.discard(dependency)

    def _auto_resolve(self, dependency: Type, additional_context: Dict[str, Any]={}) -> Any:
        """Auto-resolve dependencies from __init__ type hints."""
        req = additional_context.get(FASTAPI_REQUEST_KEY)
        if req is not None:
            import asyncio
            additional_context = asyncio.run(get_solved_dependencies(req, dependency, {})).values
            additional_context[FASTAPI_REQUEST_KEY] = req
        if isinstance(dependency, type):
            if (
                dependency.__init__ is object.__init__
            ):
                return dependency()
            init_signature = inspect.signature(dependency.__init__)
            type_hints = get_type_hints(dependency.__init__)

            resolved_deps = {}
            for param_name, param in init_signature.parameters.items():
                if param_name == "self":
                    continue
               
                if param_name in additional_context:
                    resolved_deps[param_name] = additional_context[param_name]
                    continue

                if param_name in type_hints:
                    dep_type = type_hints[param_name]
                    try:
                        resolved_deps[param_name] = self.resolve(dep_type, additional_context)
                    except ValueError as e:
                        raise ValueError(
                            f"Cannot resolve dependency for parameter '{param_name}' "
                            f"in {dependency.__name__}.__init__: {e}"
                        )
                elif param.default is not inspect.Parameter.empty:
                    # Use default value
                    continue
                raise ValueError(
                    f"Parameter '{param_name}' in {dependency.__name__}.__init__ "
                    f"has no type hint and no default value"
                    f"The parameter is: {param}"
                )
            return dependency(**resolved_deps)
       
        # Try resolves for non-class types
        if not callable(dependency):
            raise ValueError(
                f"Cannot auto-resolve non-class type: {dependency}"
            )
        call_signature = inspect.signature(dependency)
        type_hints = get_type_hints(dependency)

        resolved_deps = {}
        for param_name, param in call_signature.parameters.items():
            if param_name in type_hints:
                dep_type = type_hints[param_name]
                resolved_deps[param_name] = self.resolve(dep_type)
            elif param.default is not inspect.Parameter.empty:
                # Use default value
                continue
            else:
                if param_name in additional_context:
                    resolved_deps[param_name] = additional_context[param_name]
                else:
                    raise ValueError(
                        f"Parameter '{param_name}' in {dependency} has no type hint and no default value"
                    )
        return dependency(**resolved_deps)

    def clear(self) -> None:
        """Clear the registry (useful for testing)."""
        self._registry.clear()
        self._instances.clear()
        self._resolving.clear()


@overload
def injectable(
    _cls: Type[_T], *, scope: Scopes,
) -> Type[_TInjectable[_T]]: ...


@overload
def injectable(
    _cls: None, *, scope: Scopes,
) -> Callable[[Type[_T]], Type[_TInjectable[_T]]]: ...


def injectable(
    _cls: Optional[Type[_T]] = None,
    *,
    scope: Scopes = Scopes.TRANSIENT,
) -> Union[
    Callable[[Type[_T]], Type[_TInjectable[_T]]], Type[_TInjectable[_T]]
]:
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
    # Handle both @injectable and @injectable()
    if _cls is None:
        # Called with arguments: @injectable(scope=True)
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

        # Capture original __init__ and __new__ before any modifications
        original_init = _cls.__init__
        original_new = (
            _cls.__new__ if hasattr(_cls, "__new__") else object.__new__
        )

        # Create and attach metadata
        metadata = _InjectableMetadata(
            cls=_cls,
            scope=scope,
            dependencies=dependencies,
            original_init=original_init,
            original_new=original_new,
        )

        # Attach metadata to class (this is the only modification)
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


def Depends(dependency: Type[_TInjectable[_T]],
        *,
        use_cache: bool = True,
        container: Optional[ContainerProtocol] = None,
    ) -> _T:
    return Inject(dependency, use_cache=use_cache, container=container)