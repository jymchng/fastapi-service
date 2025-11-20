from typing import (
    Any,
    Callable,
    Dict,
    Type,
    get_type_hints,
    Optional,
    overload,
    Union,
    Generic,
)
import inspect
from functools import wraps
from dataclasses import dataclass, field

from fastapi_service.enums import Scopes
from fastapi_service.helpers import (
    _get_injectable_metadata,
    _is_injectable_instance,
)
from fastapi_service.protocols import (
    ContainerProtocol,
    MetadataProtocol,
)
from fastapi_service.typing import (
    _T,
    _TInjectable,
)
from fastapi_service.container import (
    Container,
)
from fastapi_service.additional_context_manager import (
    AdditionalContextManager,
)
from fastapi import Request


def _get_injectable_metadata(
    cls: Type[_T], container: "Optional[ContainerProtocol]" = None
) -> "Optional[MetadataProtocol[_T]]":
    """Get injectable metadata from class."""
    if container is not None:
        metadata = container.get_metadata(cls)
        if metadata is not None:
            return metadata
    if not _is_injectable_instance(cls):
        return None
    return cls.__injectable_metadata__


@dataclass
class _InjectableMetadata(Generic[_T]):
    """Metadata attached to injectable classes."""

    cls: Type[_T]
    scope: Scopes = Scopes.TRANSIENT
    dependencies: Dict[str, Type] = field(default_factory=dict)
    original_init: Optional[Callable] = None
    original_new: Optional[Callable] = None
    token: Optional[str] = None

    _instance: Optional[_T] = None

    def _dep_has_invalid_scope(
        self, dep_type: Type[_T], container: "Optional[ContainerProtocol]" = None
    ) -> None:
        """Check if a dependency is registered as singleton scope."""
        metadata = _get_injectable_metadata(dep_type, container) or False
        return not metadata or (
            isinstance(metadata, _InjectableMetadata)
            and metadata.scope > Scopes.SINGLETON
        )

    def _check_self_scope_dep_scope_are_valid(
        self, dep_type: Type[_T], container: "Optional[ContainerProtocol]" = None
    ) -> None:
        """Check if a dependency is registered as singleton scope."""
        if self.scope is Scopes.SINGLETON and self._dep_has_invalid_scope(
            dep_type, container
        ):
            raise ValueError(
                f"Cannot inject non-singleton-scoped dependency '{dep_type.__name__}' "
                f"into singleton-scoped '{self.cls.__name__}'"
            )

    def get_instance(
        self, container: "ContainerProtocol", additional_context: Dict[str, Any] = None
    ) -> Any:
        additional_context = additional_context or {}
        if self.scope is Scopes.SINGLETON:
            if self._instance is None:
                self._instance = self._create_instance(container, additional_context)
            return self._instance
        return self._create_instance(container, additional_context)

    def _create_instance(
        self, container: "ContainerProtocol", additional_context: Dict[str, Any] = {}
    ) -> Any:
        resolved_deps = {}
        additional_context_manager = AdditionalContextManager(additional_context)
        if self.original_new is not object.__new__:
            for param_name, dep_type in self.dependencies.items():
                additional_context = (
                    additional_context_manager.update_additional_context(
                        dep_type, additional_context
                    )
                )
                resolved_deps[param_name] = container.resolve(
                    dep_type, additional_context
                )
                # resolve first then check scopes
                self._check_self_scope_dep_scope_are_valid(dep_type, container)
            instance = self.original_new(self.cls, **(resolved_deps))
        else:
            instance = self.original_new(self.cls)

        if not isinstance(instance, self.cls):
            return instance

        if self.original_init is not object.__init__:
            resolved_deps = {}
            for param_name, dep_type in self.dependencies.items():
                additional_context = (
                    additional_context_manager.update_additional_context(
                        dep_type, additional_context
                    )
                )
                resolved_deps[param_name] = container.resolve(
                    dep_type, additional_context
                )
                # resolve first then check scopes
                self._check_self_scope_dep_scope_are_valid(dep_type, container)
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

        @staticmethod
        @wraps(original_new)
        def factory_new(cls_or_subcls, *args, **kwargs):
            if cls_or_subcls is not _cls:
                if original_new is not object.__new__:
                    kwargs.pop("__fastapi_request__", None)
                    return original_new(cls_or_subcls, *args, **kwargs)
                return object.__new__(cls_or_subcls)
            container = Container()
            return container.resolve(_cls, kwargs)

        @wraps(original_init)
        def factory_init(instance, *args, **kwargs):
            if type(instance) is not _cls:
                if original_new is not object.__init__:
                    kwargs.pop("__fastapi_request__", None)
                    return original_init(instance, *args, **kwargs)
                return object.__init__(instance)

        _cls.__init__ = factory_init
        _cls.__new__ = factory_new
        _cls.__new__.__signature__ = inspect.Signature(
            [
                inspect.Parameter(
                    "cls_or_subcls",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=_cls,
                ),
                inspect.Parameter(
                    "__fastapi_request__",
                    inspect.Parameter.KEYWORD_ONLY,
                    default=inspect.Parameter.empty,
                    annotation=Request,
                ),
            ]
        )

        metadata = _InjectableMetadata(
            cls=_cls,
            scope=scope,
            dependencies=dependencies,
            original_init=original_init,
            original_new=original_new,
        )

        _cls.__injectable_metadata__ = metadata

    return _cls
