from typing import TypeVar, Union

TYPE_CHECKING = False
if TYPE_CHECKING:
    from fastapi_service.protocols import InjectableProtocol

_T = TypeVar("_T")
_TInjectable = Union[_T, "InjectableProtocol[_T]"]
