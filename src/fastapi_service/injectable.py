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

    def _resolve_single_unresolved_dep(
        self,
        unresolved_dep_name: str,
        additional_context_manager: AdditionalContextManager,
    ):
        dep_type = self.dependencies[unresolved_dep_name]
        dep_type_init = dep_type.__init__
        if dep_type_init is object.__init__:
            return dep_type()
        init_signature = inspect.signature(dep_type_init)
        init_signature = init_signature.replace(
            parameters=list(init_signature.parameters.values())[1:]
        )

        def mocked_init():
            return

        mocked_init.__signature__ = init_signature
        additional_context = additional_context_manager.update_additional_context(
            mocked_init,
            dict(),
        )

        init_params_keys = list(init_signature.parameters.keys())
        additional_context_keys = list(additional_context.keys())

        init_params_keys_set = set(init_params_keys)
        additional_context_keys_set = set(additional_context_keys)

        print(
            f"`init_params_keys_set` = {init_params_keys_set}; `additional_context_keys_set` = {additional_context_keys_set}; `additional_context`: {additional_context}"
        )

        unresolved_init_deps_names = init_params_keys_set - additional_context_keys_set

        if unresolved_init_deps_names:
            raise ValueError(
                f"Cannot resolve dependency '{unresolved_dep_name}' of '{dep_type.__name__}' "
                f"because it has unresolved dependencies:`{unresolved_init_deps_names}`"
            )

        return dep_type(
            **{
                param_name: additional_context[param_name]
                for param_name in init_params_keys
            }
        )

    def _resolve_unresolved_deps(
        self,
        unresolved_deps_names: List[str],
        additional_context_manager: AdditionalContextManager,
    ):
        resolved_prev_unresolved_deps = {
            dep_name: self._resolve_single_unresolved_dep(
                dep_name, additional_context_manager
            )
            for dep_name in unresolved_deps_names
        }
        print("`resolved_prev_unresolved_deps`: ", resolved_prev_unresolved_deps)
        return resolved_prev_unresolved_deps

    def _get_additional_context_for_single_dep(
        self,
        dep_type_name: Any,
        additional_context_manager: AdditionalContextManager,
    ):
        dep_type = self.dependencies[dep_type_name]
        dep_type_init = dep_type.__init__
        if dep_type_init is object.__init__:
            return dict(dep_type_name=dep_type())
        init_signature = inspect.signature(dep_type_init)
        init_signature = init_signature.replace(
            parameters=list(init_signature.parameters.values())[1:]
        )

        def mocked_init():
            return

        mocked_init.__signature__ = init_signature
        print("MOCKED_INIT.__SIGNATURE__: ", init_signature)
        additional_context = additional_context_manager.update_additional_context(
            mocked_init,
            dict(),
        )
        return additional_context

    def _get_resolved_dependencies(
        self,
        container: "ContainerProtocol",
        additional_context: Dict[str, Any] = None,
    ):
        additional_context = additional_context or {}
        additional_context_manager = AdditionalContextManager(additional_context)

        resolved_deps = {}
        # unresolved_deps_names = []
        # using `self.dependencies` is correct because anyway it is the `__init__` parameters that has type hints
        for param_name, dep_type in self.dependencies.items():
            try:
                resolved_dep = self._resolve_single_unresolved_dep(
                    param_name, additional_context_manager
                )
            except ValueError:
                pass
            else:
                resolved_deps[param_name] = resolved_dep
            if param_name in additional_context:
                resolved_deps[param_name] = additional_context[param_name]
                continue
            additional_context = additional_context_manager.update_additional_context(
                dep_type, additional_context
            )
            print(
                "`additional_context` = ",
                additional_context,
                " dependencies: ",
                self.dependencies,
            )
            # try:
            # try resolving
            resolved_deps[param_name] = container.resolve(dep_type, additional_context)
            # except Exception:
            #     # unresolved_deps_names.append(param_name)
            #     print(f"PARAM NAME = {param_name} IS UNRESOLVED!!!")
            #     resolved_deps[param_name] = resolved_dep
            # resolve first then check scopes
            self._check_self_scope_dep_scope_are_valid(dep_type, container)
        # try getting the oracle to resolve the unresolved deps
        # resolved_prev_unresolved_deps = {}
        # if unresolved_deps_names:
        #     resolved_prev_unresolved_deps = self._resolve_unresolved_deps(
        #         unresolved_deps_names,
        #         additional_context_manager,
        #     )
        # resolved_deps.update(resolved_prev_unresolved_deps)
        print("`resolved_deps` = ", resolved_deps)
        return resolved_deps

    def _create_instance(
        self, container: "ContainerProtocol", additional_context: Dict[str, Any] = None
    ) -> Any:
        additional_context = additional_context or {}
        print("`_created_instance`'s `self` = ", self)
        print(
            "`additional_context` = ",
            additional_context,
            " dependencies: ",
            self.dependencies,
        )
        if self.original_new is not OBJECT_NEW_FUNC:
            print("self.original_new is not OBJECT_NEW_FUNC")
            instance = self.original_new(
                self.cls,
                **(self._get_resolved_dependencies(container, additional_context)),
            )

        else:
            instance = self.original_new(self.cls)

        if not isinstance(instance, self.cls):
            print(
                "if not isinstance(instance, self.cls): ",
                instance,
                self.cls,
                isinstance(instance, self.cls),
            )
            return instance

        if self.original_init is not OBJECT_INIT_FUNC:
            original_init_signature = inspect.signature(self.original_init)
            print(
                "self.original_init is not OBJECT_INIT_FUNC! ",
                f" `self.cls` = {self.cls} ",
                "`additional_context` = ",
                additional_context,
                " dependencies: ",
                self.dependencies,
                " original_init_signature: ",
                original_init_signature,
            )
            resolved_deps = self._get_resolved_dependencies(
                container, additional_context
            )
            print("`resolved_deps` = ", resolved_deps)
            self.original_init(instance, **resolved_deps)
        else:
            print("self.original_init is OBJECT_INIT_FUNC")
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

    if hasattr(_cls, DUNDER_INIT_KEY):
        init_signature = inspect.signature(_cls.__init__)
        type_hints = get_type_hints(_cls.__init__)

        init_signature = init_signature.replace(
            parameters=list(init_signature.parameters.values())[1:]
        )
        dependencies = _get_dependencies_from_signature(init_signature, type_hints)

        print("`dependencies`: ", dependencies)
        original_init = _cls.__init__
        original_new = (
            _cls.__new__ if hasattr(_cls, DUNDER_NEW_KEY) else OBJECT_NEW_FUNC
        )

        @staticmethod
        @wraps(original_new)
        def factory_new(cls_or_subcls, *args, **kwargs):
            if cls_or_subcls is not _cls:
                if original_new is not OBJECT_NEW_FUNC:
                    kwargs.pop(FASTAPI_REQUEST_KEY, None)
                    return original_new(cls_or_subcls, *args, **kwargs)
                return OBJECT_NEW_FUNC(cls_or_subcls)
            container = Container()
            return container.resolve(_cls, kwargs)

        @wraps(original_init)
        def factory_init(instance, *args, **kwargs):
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
        )

        _cls.__injectable_metadata__ = metadata

    return _cls
