from typing import TypeVar, Union


TYPE_CHECKING = False
if TYPE_CHECKING:
    from fastapi_service.protocols import (
        InjectableProtocol,
        MetadataProtocol,
        ContainerProtocol,
        OracleProtocol,
    )

_T_co = TypeVar("_T_co", covariant=True)
_T_contra = TypeVar("_T_contra", contravariant=True)
_T = TypeVar("_T")


_TOracle = TypeVar("_TOracle", bound="OracleProtocol")
"""`_TOracle` is a type variable bound to `OracleProtocol`."""


_TMetadata = TypeVar("_TMetadata", bound="MetadataProtocol")
"""`_TMetadata` is a type variable bound to `MetadataProtocol`."""


_TContainer = TypeVar("_TContainer", bound="ContainerProtocol")
"""`_TContainer` is a type variable bound to `ContainerProtocol`."""


_TInjectable = Union["MetadataProtocol[_T]", _T, "InjectableProtocol[_T]"]
