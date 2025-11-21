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
        import inspect

        original_additional_context = additional_context
        if self.__fastapi_request__ is not None:
            try:
                additional_context = asyncio.run(
                    get_solved_dependencies(self.__fastapi_request__, dependency, {})
                ).values
                additional_context[FASTAPI_REQUEST_KEY] = self.__fastapi_request__
                print(
                    f"28: Dependencies solved by FastAPI: `additional_context`: {additional_context}; `dependency`: {dependency}, "
                    f"signature: {inspect.signature(dependency)}"
                )
            except Exception as err:
                print(
                    "Exception occurred: ",
                    err,
                    " dependency: ",
                    dependency,
                    " signature: ",
                    inspect.signature(dependency),
                )
                original_additional_context[FASTAPI_REQUEST_KEY] = (
                    self.__fastapi_request__
                )
                return original_additional_context
        return additional_context
