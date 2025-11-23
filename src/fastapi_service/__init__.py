from fastapi import Depends
from fastapi_service.injectable import injectable
from fastapi_service.container import Container
from fastapi_service.enums import Scopes

__all__ = [
    "Depends",
    "injectable",
    "Container",
    "Scopes",
]

__version__ = "0.1.0"
