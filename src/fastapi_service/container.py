from typing import (
    Any,
    Dict,
    Type,
    get_type_hints,
)
from dataclasses import dataclass, field
import inspect
import asyncio

from fastapi_service.helpers import (
    get_solved_dependencies,
    _is_injectable_instance,
)
from fastapi_service.constants import (
    FASTAPI_REQUEST_KEY,
)
from fastapi_service.typing import (
    _T,
    _TInjectable,
)

TYPE_CHECKING = False

if TYPE_CHECKING:
    from fastapi_service.injectable import _InjectableMetadata


@dataclass
class Container:
    """Dependency injection container."""

    _registry: Dict[Type, "_InjectableMetadata"] = field(default_factory=dict)
    _instances: Dict[Type[_TInjectable[_T]], _T] = field(default_factory=dict)
    _resolving: set = field(
        default_factory=set
    )  # Track currently resolving dependencies

    def resolve(
        self,
        dependency: Type[_TInjectable[_T]],
        additional_context: Dict[str, Any] = {},
    ) -> _T:
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

    def _auto_resolve(
        self, dependency: Any, additional_context: Dict[str, Any] = {}
    ) -> Any:
        """Auto-resolve dependencies from __init__ type hints."""
        req = additional_context.get(FASTAPI_REQUEST_KEY)
        if req is not None:
            additional_context = asyncio.run(
                get_solved_dependencies(req, dependency, {})
            ).values
            additional_context[FASTAPI_REQUEST_KEY] = req
        if isinstance(dependency, type):
            if dependency.__init__ is object.__init__:
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
                        resolved_deps[param_name] = self.resolve(
                            dep_type, additional_context
                        )
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
            raise ValueError(f"Cannot auto-resolve non-class type: {dependency}")
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
