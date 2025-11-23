from typing import Optional, Dict, Any, Type
import asyncio
from dataclasses import dataclass

from fastapi import Request
from fastapi_service.helpers import get_solved_dependencies
from fastapi_service.typing import _T, _TInjectable, _TOracle


@dataclass
class FastAPIOracle:
    __slots__ = (
        "__fastapi_request__",
        "dependency_cache",
    )

    def __init__(self, request: Request):
        self.__fastapi_request__ = request
        self.dependency_cache = dict()

    def get_context(
        self,
        dependency: _TInjectable,
    ) -> Dict[str, Any]:
        """Oracle returns additional context for resolving a `dependency`."""
        additional_context = {}
        if self.__fastapi_request__ is not None:
            try:
                additional_context = asyncio.run(
                    get_solved_dependencies(
                        self.__fastapi_request__, dependency, self.dependency_cache
                    )
                ).values
            except Exception:
                ...  # Ignore errors and return empty context
        return additional_context


@dataclass
class NullOracle:
    __slots__ = ()

    def get_context(
        self,
        dependency: _TInjectable,
    ) -> Dict[str, Any]:
        """Oracle returns additional context for resolving a `dependency`."""
        return {}
