from typing import Protocol, Dict, Any, runtime_checkable, Optional
from inspect import Signature

from fastapi_service.typing import _T, _TInjectable, _TOracle, _TMetadata


@runtime_checkable
class InjectableProtocol(Protocol[_T]):
    """Protocol for injectable classes."""

    __injectable_metadata__: "MetadataProtocol[_T]"


@runtime_checkable
class ContainerProtocol(Protocol):
    """Protocol for dependency injection container."""

    def resolve(
        self,
        dependency: _TInjectable,
        oracle: _TOracle,
    ) -> _T: ...

    def get_metadata(self, cls: _TInjectable) -> Optional[_TMetadata]: ...

    def clear(self) -> None: ...


@runtime_checkable
class MetadataProtocol(Protocol[_T]):
    """Protocol for dependency injection container."""

    def owned_by(
        self,
    ) -> _TInjectable[_T]: ...

    def get_instance(
        self,
        container: ContainerProtocol,
        additional_context: Dict[str, Any],
    ) -> _T: ...


@runtime_checkable
class OracleProtocol(Protocol[_T]):
    """Oracles magically has the solution to resolving a `dependency`."""

    def get_context(
        self,
        dependency: _TInjectable,
    ) -> Dict[str, Any]:
        """Oracle returns additional context for resolving a `dependency`."""
        ...


@runtime_checkable
class HasSignature(Protocol):
    __signature__: Signature
