from typing import Protocol, Type, Dict, Any, runtime_checkable, Optional

from fastapi_service.typing import _T, _TInjectable


@runtime_checkable
class InjectableProtocol(Protocol[_T]):
    """Protocol for injectable classes."""

    __injectable_metadata__: "MetadataProtocol[_T]"


@runtime_checkable
class ContainerProtocol(Protocol):
    """Protocol for dependency injection container."""

    def resolve(
        self, dependency: Type[_TInjectable[_T]], additional_context: Dict[str, Any]
    ) -> _T: ...

    def get_metadata(self, cls: Type[_T]) -> Optional["MetadataProtocol[_T]"]: ...

    def clear(self) -> None: ...


@runtime_checkable
class MetadataProtocol(Protocol[_T]):
    """Protocol for dependency injection container."""

    def get_instance(
        self, container: ContainerProtocol, additional_context: Dict[str, Any]
    ) -> _T: ...
