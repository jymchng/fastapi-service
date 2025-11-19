from typing import Protocol, Type, Dict, Any, runtime_checkable

from fastapi_service.typing import _T, _TInjectable

@runtime_checkable
class InjectableProtocol(Protocol[_T]):
    """Protocol for injectable classes."""

    __injectable_metadata__: "_InjectableMetadata"


@runtime_checkable
class ContainerProtocol(Protocol):
    """Protocol for dependency injection container."""

    def resolve(self, dependency: Type[_TInjectable[_T]], additional_context: Dict[str, Any]) -> _T: ...

    def clear(self) -> None: ...
