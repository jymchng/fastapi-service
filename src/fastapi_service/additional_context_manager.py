from typing import Optional, Dict, Any, Type
import asyncio
from dataclasses import dataclass

from fastapi import Request
from fastapi_service.constants import FASTAPI_REQUEST_KEY
from fastapi_service.helpers import get_solved_dependencies
from fastapi_service.typing import _T


@dataclass
class AdditionalContextManager:
    __fastapi_request__: Optional[Request] = None

    def __init__(self, kwargs: Dict[str, Any]):
        self.__fastapi_request__ = kwargs.pop(FASTAPI_REQUEST_KEY, None)

    def update_additional_context(
        self, dependency: Type[_T], additional_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        if self.__fastapi_request__ is not None:
            additional_context = asyncio.run(
                get_solved_dependencies(self.__fastapi_request__, dependency, {})
            ).values
        return additional_context
