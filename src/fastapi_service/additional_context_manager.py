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
        self.__fastapi_request__ = kwargs.get(FASTAPI_REQUEST_KEY)
        self.dependency_cache = dict()

    def update_additional_context(
        self, dependency: Type[_T], additional_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        original_additional_context = {k: v for k, v in additional_context.items()}
        if self.__fastapi_request__ is not None:
            try:
                additional_context = asyncio.run(
                    get_solved_dependencies(
                        self.__fastapi_request__, dependency, self.dependency_cache
                    )
                ).values
                additional_context[FASTAPI_REQUEST_KEY] = self.__fastapi_request__
            except Exception:
                original_additional_context[FASTAPI_REQUEST_KEY] = (
                    self.__fastapi_request__
                )
                return original_additional_context
        return additional_context
