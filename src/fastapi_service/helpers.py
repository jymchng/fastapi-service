import json
import re
from contextlib import AsyncExitStack
from typing import Any, Callable, Optional, Type, Dict
import email.message
import inspect
from typing_extensions import TypeIs

from fastapi import HTTPException, Request, params
from fastapi._compat import ModelField, Undefined
from fastapi.dependencies.models import Dependant
from fastapi.dependencies.utils import (
    _should_embed_body_fields,
    get_body_field,
    get_dependant,
    get_flat_dependant,
    solve_dependencies,
)
from fastapi.exceptions import RequestValidationError
from fastapi.routing import compile_path, get_name
from fastapi_service.protocols import InjectableProtocol
from fastapi_service.typing import _T


def _make_fake_function_with_same_signature(
    signature: inspect.Signature,
):
    def fake_function(): ...

    fake_function.__signature__ = signature
    return fake_function


def _remove_first_param_from_init_or_new_func_signature(
    new_or_init_func: Callable,
):
    return _remove_first_n_param_from_signature(
        signature_=inspect.signature(new_or_init_func),
        n=1,
    )


def _remove_first_n_param_from_signature(
    signature_: inspect.Signature,
    n: int = 1,
):
    return signature_.replace(parameters=list(signature_.parameters.values())[n:])


def _get_dependencies_from_signature(
    signature_: inspect.Signature, type_hints: dict[str, Any]
) -> Dict[str, Optional[Any]]:
    # from fastapi_service.injectable import _InjectableMetadata

    return {
        name: type_hints.get(name)
        for name, _ in list(signature_.parameters.items())
        # if param.default is inspect.Parameter.empty
        # or isinstance(param.default, (params.Depends, _InjectableMetadata, params.FieldInfo, params.Param))
    }


def generate_unique_id_for_dependant(dependant: Dependant, path_format: str):
    name = get_name(dependant.call)
    operation_id = f"{name}{path_format}"
    operation_id = re.sub(r"\W", "_", operation_id)
    return operation_id


async def get_body_field_should_embed_from_request(
    dependant: Dependant, path_format: str
) -> tuple[Optional[ModelField], bool]:
    flat_dependant = get_flat_dependant(dependant)
    embed_body_fields = _should_embed_body_fields(flat_dependant.body_params)
    body_field = get_body_field(
        flat_dependant=flat_dependant,
        name=generate_unique_id_for_dependant(dependant, path_format),
        embed_body_fields=embed_body_fields,
    )
    return body_field, embed_body_fields


async def get_body_from_request(
    request: Request, body_field: Optional[ModelField] = None
):
    body: Any = None
    is_body_form = body_field and isinstance(body_field.field_info, params.Form)
    async with AsyncExitStack() as file_stack:
        try:
            body: Any = None
            if body_field:
                if is_body_form:
                    body = await request.form()
                    file_stack.push_async_callback(body.close)
                else:
                    body_bytes = await request.body()
                    if body_bytes:
                        json_body: Any = Undefined
                        content_type_value = request.headers.get("content-type")
                        if not content_type_value:
                            json_body = await request.json()
                        else:
                            message = email.message.Message()
                            message["content-type"] = content_type_value
                            if message.get_content_maintype() == "application":
                                subtype = message.get_content_subtype()
                                if subtype == "json" or subtype.endswith("+json"):
                                    json_body = await request.json()
                        if json_body != Undefined:
                            body = json_body
                        else:
                            body = body_bytes
        except json.JSONDecodeError as e:
            validation_error = RequestValidationError(
                [
                    {
                        "type": "json_invalid",
                        "loc": ("body", e.pos),
                        "msg": "JSON decode error",
                        "input": {},
                        "ctx": {"error": e.msg},
                    }
                ],
                body=e.doc,
            )
            raise validation_error from e
        except HTTPException:
            # If a middleware raises an HTTPException, it should be raised again
            raise
        except Exception as e:
            http_error = HTTPException(
                status_code=400, detail="There was an error parsing the body"
            )
            raise http_error from e
    return body


async def get_solved_dependencies(
    request: Request,
    endpoint: Callable,
    dependency_cache: dict,
):
    _, path_format, _ = compile_path(request.url.path)
    endpoint_dependant = get_dependant(path=path_format, call=endpoint)
    (
        body_field,
        should_embed_body_fields,
    ) = await get_body_field_should_embed_from_request(endpoint_dependant, path_format)
    body = await get_body_from_request(request, body_field)
    async with AsyncExitStack() as stack:
        endpoint_solved_dependencies = await solve_dependencies(
            request=request,
            dependant=endpoint_dependant,
            async_exit_stack=stack,
            embed_body_fields=should_embed_body_fields,
            body=body,
            dependency_cache=dependency_cache,
        )
    return endpoint_solved_dependencies


def _is_injectable_instance(obj: Any) -> TypeIs[InjectableProtocol]:
    """Check if an object is an instance of an injectable class."""
    return isinstance(obj, InjectableProtocol)


def _get_injectable_metadata(cls: Type[_T]) -> "Optional[_InjectableMetadata[_T]]":
    """Get injectable metadata from class."""
    if not _is_injectable_instance(cls):
        return None
    return cls.__injectable_metadata__
