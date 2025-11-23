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
    _make_fake_function_with_same_signature,
    _remove_first_n_param_from_signature,
)
from fastapi_service.typing import (
    _T,
    _TInjectable,
)
from fastapi_service.protocols import (
    MetadataProtocol,
    OracleProtocol,
)
from fastapi_service.enums import Scopes
from fastapi_service.constants import (
    DUNDER_INIT_KEY,
    DUNDER_NEW_KEY,
    OBJECT_INIT_FUNC,
    OBJECT_NEW_FUNC,
)
from fastapi_service.oracle import NullOracle


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
        oracle: "OracleProtocol[_T]" = NullOracle(),
    ) -> _T:
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
                    return metadata.get_instance(self, oracle)

            if isinstance(dependency, MetadataProtocol):
                return dependency.get_instance(self, oracle)

            if dependency in self._registry:
                metadata = self._registry[dependency]
                return metadata.get_instance(self, oracle)

            if _is_injectable_instance(dependency):
                metadata = dependency.__injectable_metadata__
                metadata_owner = metadata.owned_by()
                if metadata_owner is dependency:
                    self._registry[metadata_owner] = metadata
                    return metadata.get_instance(self, oracle)

            return self._auto_resolve(dependency, oracle)

        finally:
            self._resolving.discard(dependency)

    def _auto_resolve_by_class(
        self,
        dependency: Type[_T],
        oracle: "OracleProtocol[_T]",
    ):
        from fastapi_service.injectable import _InjectableMetadata

        initializer = dependency.__init__
        if initializer is OBJECT_INIT_FUNC:
            original_new = getattr(dependency, DUNDER_NEW_KEY, OBJECT_NEW_FUNC)
            original_new_signature = inspect.signature(original_new)
            original_new_params = original_new_signature.parameters
            metadata = _InjectableMetadata(
                cls=dependency,
                # auto_resolved dependency, i.e. not decorated with `@singleton(scope=Scopes.SINGLETON)`
                # are always transient
                scope=Scopes.TRANSIENT,
                dependencies={},
                original_init=OBJECT_INIT_FUNC,
                original_new=original_new,
                original_new_params=original_new_params,
            )
            self._registry[dependency] = metadata

            return dependency()
        # dependency.__init__ is NOT object.__init__
        intializer_signature = inspect.signature(initializer)
        init_signature_without_self = _remove_first_n_param_from_signature(
            intializer_signature
        )
        fake_function_with_same_signature = _make_fake_function_with_same_signature(
            init_signature_without_self
        )
        additional_context = oracle.get_context(fake_function_with_same_signature)
        type_hints = get_type_hints(initializer)

        resolved_deps = {}
        # metadata_scope = Scopes.SINGLETON
        for param_name, param in init_signature_without_self.parameters.items():
            # found in oracle, good
            if param_name in additional_context:
                # even if param.default is not empty, value in additional_context takes priority
                # because it is oracle
                resolved_deps[param_name] = additional_context[param_name]
                continue

            # has default value, good, but cannot be like `Depends` etc
            if param.default is not inspect.Parameter.empty:
                resolved_deps[param_name] = param.default
                continue

            if param is None or param_name not in type_hints:
                raise ValueError(
                    f"Cannot resolve dependency for parameter '{param_name}' "
                    f"in {dependency.__name__}.{DUNDER_INIT_KEY}: type hint is missing."
                )

            if param_name in type_hints:
                dep_type = type_hints[param_name]
                try:
                    resolved_deps[param_name] = self.resolve(dep_type, oracle)
                    # param_metadata = self._registry.get(dep_type)
                    # if param_metadata is not None:
                    #     metadata_scope = max(metadata_scope, param_metadata.scope)
                except ValueError as e:
                    raise ValueError(
                        f"Cannot resolve dependency for parameter '{param_name}' "
                        f"in {dependency.__name__}.{DUNDER_INIT_KEY}."
                    ) from e
            else:
                raise ValueError(
                    f"Parameter '{param_name}' in {dependency.__name__}.{DUNDER_INIT_KEY} "
                    f"has no type hint and no default value. "
                    f"The parameter is: {param}. "
                    f"Type hints: {type_hints}."
                )
        metadata = _InjectableMetadata._from_class(
            klass=dependency, scope=Scopes.TRANSIENT
        )
        self._registry[dependency] = metadata
        return dependency(**resolved_deps)

    def _auto_resolve(
        self,
        dependency: Type,
        oracle: OracleProtocol[_T],
    ) -> Any:
        from fastapi_service.injectable import _InjectableMetadata

        if isinstance(dependency, type):
            return self._auto_resolve_by_class(dependency, oracle)

        if not callable(dependency):
            raise ValueError(f"Cannot auto-resolve non-class type: {dependency}")

        additional_context = oracle.get_context(dependency)
        call_signature = inspect.signature(dependency)
        type_hints = get_type_hints(dependency)

        dependencies = _get_dependencies_from_signature(call_signature, type_hints)
        resolved_deps = {}
        metadata_scope = Scopes.SINGLETON
        for param_name, param in call_signature.parameters.items():
            # found in oracle, good
            if param_name in additional_context:
                # even if param.default is not empty, value in additional_context takes priority
                # because it is oracle
                resolved_deps[param_name] = additional_context[param_name]
                continue

            # has default value, good, but cannot be like `Depends` etc
            if param.default is not inspect.Parameter.empty:
                resolved_deps[param_name] = param.default
                continue

            if param is None or param_name not in type_hints:
                raise ValueError(
                    f"Cannot resolve dependency for parameter '{param_name}' "
                    f"in {dependency.__name__}: type hint is missing."
                )

            if param_name in type_hints:
                dep_type = type_hints[param_name]
                try:
                    resolved_deps[param_name] = self.resolve(dep_type, oracle)
                    param_metadata = self._registry.get(dep_type)
                    if param_metadata is not None:
                        metadata_scope = max(metadata_scope, param_metadata.scope)
                except ValueError as e:
                    raise ValueError(
                        f"Cannot resolve dependency for parameter '{param_name}' "
                        f"in {dependency.__name__}.{DUNDER_INIT_KEY}."
                    ) from e
            else:
                raise ValueError(
                    f"Parameter '{param_name}' in {dependency.__name__}.{DUNDER_INIT_KEY} "
                    f"has no type hint and no default value. "
                    f"The parameter is: {param}. "
                    f"Type hints: {type_hints}."
                )
        original_init = (
            dependency.__init__
            if hasattr(dependency, DUNDER_INIT_KEY)
            else OBJECT_INIT_FUNC
        )
        original_new = (
            dependency.__new__
            if hasattr(dependency, DUNDER_NEW_KEY)
            else OBJECT_NEW_FUNC
        )

        metadata = _InjectableMetadata(
            cls=dependency,
            scope=metadata_scope,
            dependencies=dependencies,
            original_init=original_init,
            original_new=original_new,
        )
        self._registry[dependency] = metadata
        return dependency(**resolved_deps)

    def clear(self) -> None:
        """Clear the registry (useful for testing)."""
        self._registry.clear()
        self._instances.clear()
        self._resolving.clear()
