from typing import TypeVar, Union


TYPE_CHECKING = False
if TYPE_CHECKING:
    from fastapi_service.protocols import InjectableProtocol, MetadataProtocol

_T = TypeVar("_T")
_TInjectable = Union["InjectableProtocol[_T]", _T, "MetadataProtocol[_T]"]
