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
    List,
)
import inspect
from functools import wraps
from dataclasses import dataclass, field

from fastapi_service.enums import Scopes
from fastapi_service.helpers import (
    _get_injectable_metadata,
    _is_injectable_instance,
    _get_dependencies_from_signature,
    _remove_first_n_param_from_signature,
    _make_fake_function_with_same_signature,
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
from fastapi_service.constants import (
    DUNDER_INIT_KEY,
    DUNDER_NEW_KEY,
    OBJECT_INIT_FUNC,
    OBJECT_NEW_FUNC,
    FASTAPI_REQUEST_KEY,
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
    original_init_params: Optional[Dict[str, inspect.Parameter]] = field(
        default_factory=dict
    )
    original_new: Optional[Callable] = None
    original_new_params: Optional[Dict[str, inspect.Parameter]] = field(
        default_factory=dict
    )
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
        self,
        container: "ContainerProtocol",
        additional_context: Dict[str, Any] = None,
    ) -> Any:
        additional_context = additional_context or {}
        if self.scope is Scopes.SINGLETON:
            if self._instance is None:
                instance = self._create_instance(container, additional_context)
                self._init_instance(instance, container, additional_context)
                self._instance = instance
            return self._instance
        instance = self._create_instance(container, additional_context)
        self._init_instance(instance, container, additional_context)
        return instance

    def _get_resolved_dependencies_from_oracle(
        self,
        additional_context: Dict[str, Any],
        additional_context_manager: AdditionalContextManager,
    ):
        init_signature = inspect.signature(self.original_init)
        init_signature_with_first_param_removed = _remove_first_n_param_from_signature(
            init_signature
        )
        fake_function_with_same_signature = _make_fake_function_with_same_signature(
            init_signature_with_first_param_removed
        )
        additional_context = additional_context_manager.update_additional_context(
            fake_function_with_same_signature,
            additional_context,
        )
        return additional_context

    def _get_resolved_dependencies(
        self,
        container: "ContainerProtocol",
        additional_context: Dict[str, Any] = None,
    ):
        additional_context = additional_context or {}
        additional_context_manager = AdditionalContextManager(additional_context)

        additional_context = self._get_resolved_dependencies_from_oracle(
            additional_context, additional_context_manager
        )
        resolved_deps = {}

        # using `self.dependencies` is correct because
        # #anyway it is the `__init__` parameters that has type hints
        for param_name, dep_type in self.dependencies.items():
            if param_name in additional_context:
                resolved_deps[param_name] = additional_context[param_name]
                if self.scope is Scopes.SINGLETON:
                    raise ValueError(
                        f"Cannot inject non-singleton-scoped dependency '{param_name}' "
                        f"into singleton-scoped '{self.cls.__name__}'"
                    )
                continue
            parameter = self.original_init_params.get(param_name)
            default_param_value = (
                parameter.default if parameter is not None else inspect.Parameter.empty
            )
            if default_param_value is not inspect.Parameter.empty:
                resolved_deps[param_name] = default_param_value
                continue
            additional_context = additional_context_manager.update_additional_context(
                dep_type, additional_context
            )
            try:
                resolved_deps[param_name] = container.resolve(
                    dep_type, additional_context
                )
            except Exception as err:
                dep_type_name = getattr(
                    dep_type, "__name__", "<unknown>" if dep_type else dep_type
                )
                raise ValueError(
                    f"Parameter with name `{param_name}` and type hint `{dep_type_name}`"
                    f"cannot be resolved due to: "
                    f"{err}"
                ) from err
            self._check_self_scope_dep_scope_are_valid(dep_type, container)
        return resolved_deps

    def _create_instance(
        self, container: "ContainerProtocol", additional_context: Dict[str, Any] = None
    ) -> _T:
        additional_context = additional_context or {}
        if self.original_new is not OBJECT_NEW_FUNC:
            instance = self.original_new(
                self.cls,
                **(self._get_resolved_dependencies(container, additional_context)),
            )
        else:
            instance = self.original_new(self.cls)
        return instance

    def _init_instance(
        self,
        instance: _T,
        container: "ContainerProtocol",
        additional_context: Dict[str, Any] = None,
    ) -> _T:
        additional_context = additional_context or {}
        if self.original_init is not OBJECT_INIT_FUNC:
            resolved_deps = self._get_resolved_dependencies(
                container, additional_context
            )
            self.original_init(instance, **resolved_deps)
        else:
            self.original_init(instance)


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

    if hasattr(_cls, DUNDER_INIT_KEY):
        original_init = _cls.__init__
        original_new = (
            _cls.__new__ if hasattr(_cls, DUNDER_NEW_KEY) else OBJECT_NEW_FUNC
        )

        ctor_signature = inspect.signature(original_new)
        ctor_signature_params = ctor_signature.parameters

        init_signature = inspect.signature(original_init)
        init_signature_params = init_signature.parameters
        type_hints = get_type_hints(_cls.__init__)

        init_signature_with_first_param_removed = _remove_first_n_param_from_signature(
            init_signature
        )
        dependencies = _get_dependencies_from_signature(
            init_signature_with_first_param_removed, type_hints
        )

        @staticmethod
        @wraps(original_new)
        def factory_new(cls_or_subcls, *args, **kwargs):
            if FASTAPI_REQUEST_KEY not in kwargs:
                # means we are instantiating it as a normal ass
                if original_new is not OBJECT_NEW_FUNC:
                    return original_new(cls_or_subcls, *args, **kwargs)
                return OBJECT_NEW_FUNC(cls_or_subcls)
            # here we are not instantiating it as a normal class
            # `Depends` is instantiating it
            if cls_or_subcls is not _cls:
                # means `cls_or_subcls` is subcls of `_cls`
                subcls = cls_or_subcls
                if original_new is not OBJECT_NEW_FUNC:
                    # `Depends` can still inject the `Request` object into `**kwargs`
                    # so we take it out
                    kwargs.pop(FASTAPI_REQUEST_KEY, None)
                    return original_new(subcls, *args, **kwargs)
                return OBJECT_NEW_FUNC(subcls)
            # the actual `_cls`
            container = Container()
            return container.resolve(_cls, kwargs)

        @wraps(original_init)
        def factory_init(instance, *args, **kwargs):
            if FASTAPI_REQUEST_KEY not in kwargs:
                # means we are instantiating it as a normal ass
                if original_new is not OBJECT_INIT_FUNC:
                    return original_init(instance, *args, **kwargs)
                return OBJECT_INIT_FUNC(instance)
            if type(instance) is not _cls:
                if original_new is not OBJECT_INIT_FUNC:
                    kwargs.pop(FASTAPI_REQUEST_KEY, None)
                    return original_init(instance, *args, **kwargs)
                return OBJECT_INIT_FUNC(instance)

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
                    FASTAPI_REQUEST_KEY,
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
            original_init_params=init_signature_params,
            original_new_params=ctor_signature_params,
        )
        _cls.__injectable_metadata__ = metadata

    return _cls
