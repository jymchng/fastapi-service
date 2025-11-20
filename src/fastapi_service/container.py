from typing import (
    Any,
    Dict,
    Type,
    get_type_hints,
    Optional,
)
from dataclasses import dataclass, field
import inspect

from fastapi_service.helpers import (
    _is_injectable_instance,
    _get_dependencies_from_signature,
)
from fastapi_service.typing import (
    _T,
    _TInjectable,
)
from fastapi_service.protocols import (
    MetadataProtocol,
)
from fastapi_service.enums import Scopes
from fastapi_service.additional_context_manager import AdditionalContextManager


@dataclass
class Container:
    """Dependency injection container."""

    _registry: Dict[Type, MetadataProtocol[_T]] = field(default_factory=dict)
    _instances: Dict[Type[_TInjectable[_T]], _T] = field(default_factory=dict)
    _resolving: set = field(
        default_factory=set
    )  # Track currently resolving dependencies
    _token_metadata_registry: Dict[str, MetadataProtocol] = field(default_factory=dict)

    def get_metadata(self, cls: Type[_T]) -> Optional["MetadataProtocol[_T]"]:
        """Get injectable metadata from class."""
        if cls in self._registry:
            return self._registry[cls]
        if not _is_injectable_instance(cls):
            return None
        return cls.__injectable_metadata__

    def resolve(
        self,
        dependency: Type[_TInjectable[_T]],
        additional_context: Dict[str, Any] = None,
    ) -> _T:
        additional_context = additional_context or {}
        if dependency in self._resolving:
            chain = " -> ".join([d.__name__ for d in self._resolving])
            raise ValueError(
                f"Circular dependency detected: {chain} -> {dependency.__name__}"
            )

        try:
            self._resolving.add(dependency)

            if isinstance(dependency, str):
                if dependency in self._token_metadata_registry:
                    metadata = self._token_metadata_registry[dependency]
                    return metadata.get_instance(self, additional_context)

            if isinstance(dependency, MetadataProtocol):
                return dependency.get_instance(self, additional_context)

            if dependency in self._registry:
                metadata = self._registry[dependency]
                return metadata.get_instance(self, additional_context)

            if _is_injectable_instance(dependency):
                metadata = dependency.__injectable_metadata__
                if metadata.cls is dependency:
                    self._registry[metadata.cls] = metadata
                    return metadata.get_instance(self, additional_context)

            return self._auto_resolve(dependency, additional_context)

        finally:
            self._resolving.discard(dependency)

    def _auto_resolve(
        self, dependency: Type, additional_context: Dict[str, Any] = {}
    ) -> Any:
        additional_context_manager = AdditionalContextManager(additional_context)
        additional_context = additional_context_manager.update_additional_context(
            dependency, additional_context
        )
        from fastapi_service.injectable import _InjectableMetadata

        if isinstance(dependency, type):
            print("isinstance(dependency, type) is True; `dependency` = ", dependency)
            if dependency.__init__ is object.__init__:
                metadata = _InjectableMetadata(
                    cls=dependency,
                    scope=Scopes.SINGLETON,
                    dependencies={},
                    original_init=object.__init__,
                    original_new=getattr(dependency, "__new__", object.__new__),
                )
                self._registry[dependency] = metadata

                return dependency()

            init_signature = inspect.signature(dependency.__init__)
            type_hints = get_type_hints(dependency.__init__)

            init_signature = init_signature.replace(
                parameters=list(init_signature.parameters.values())[1:]
            )
            dependencies = _get_dependencies_from_signature(init_signature, type_hints)
            resolved_deps = {}
            metadata_scope = Scopes.SINGLETON
            for param_name, param in init_signature.parameters.items():
                # found in oracle, good
                if param_name in additional_context:
                    # even if param.default is not empty, value in additional_context takes priority
                    # because it is oracle
                    all_deps_are_singleton = False
                    resolved_deps[param_name] = additional_context[param_name]
                    continue

                # has default value, good, but cannot be like `Depends` etc
                if param.default is not inspect.Parameter.empty:
                    resolved_deps[param_name] = param.default
                    continue

                if param is None or param_name not in type_hints:
                    raise ValueError(
                        f"Cannot resolve dependency for parameter '{param_name}' "
                        f"in {dependency.__name__}.__init__: type hint is missing."
                    )

                if param_name in type_hints:
                    dep_type = type_hints[param_name]
                    try:
                        resolved_deps[param_name] = self.resolve(
                            dep_type, additional_context
                        )
                        param_metadata = self._registry.get(dep_type)
                        if param_metadata is not None:
                            metadata_scope = max(metadata_scope, param_metadata.scope)
                    except ValueError as e:
                        raise ValueError(
                            f"Cannot resolve dependency for parameter '{param_name}' "
                            f"in {dependency.__name__}.__init__."
                        ) from e
                else:
                    raise ValueError(
                        f"Parameter '{param_name}' in {dependency.__name__}.__init__ "
                        f"has no type hint and no default value. "
                        f"The parameter is: {param}. "
                        f"Type hints: {type_hints}."
                    )
            metadata = _InjectableMetadata(
                cls=dependency,
                scope=metadata_scope,
                dependencies=dependencies,
                original_init=dependency.__init__,
                original_new=getattr(dependency, "__new__", object.__new__),
            )
            print(
                "`dependency`: ",
                dependency,
                " `dependencies`: ",
                dependencies,
                " `resolved_deps`: ",
                resolved_deps,
            )
            self._registry[dependency] = metadata
            return dependency(**resolved_deps)

        if not callable(dependency):
            raise ValueError(f"Cannot auto-resolve non-class type: {dependency}")

        call_signature = inspect.signature(dependency)
        type_hints = get_type_hints(dependency)

        dependencies = _get_dependencies_from_signature(call_signature, type_hints)
        resolved_deps = {}
        all_deps_are_singleton = True
        for param_name, param in dependencies.items():
            if param is None:
                raise ValueError(
                    f"Cannot resolve dependency for parameter '{param_name}' "
                    f"in {dependency.__name__}: type hint is missing."
                )
            if param_name in type_hints:
                dep_type = type_hints[param_name]
                resolved_deps[param_name] = self.resolve(dep_type)
            elif param_name in additional_context:
                all_deps_are_singleton = False
                resolved_deps[param_name] = additional_context[param_name]
            elif param.default is not inspect.Parameter.empty:
                continue
            else:
                raise ValueError(
                    f"Parameter '{param_name}' in {dependency} has no type hint and no default value"
                )
        metadata = _InjectableMetadata(
            cls=dependency,
            scope=Scopes.SINGLETON if all_deps_are_singleton else Scopes.TRANSIENT,
            dependencies=dependencies,
            original_init=None,
            original_new=dependency,
        )
        self._registry[dependency] = metadata
        return dependency(**resolved_deps)

    def clear(self) -> None:
        """Clear the registry (useful for testing)."""
        self._registry.clear()
        self._instances.clear()
        self._resolving.clear()
