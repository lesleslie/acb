"""Utility helpers for MCP components and tools.

These helpers are intentionally lightweight to keep tests hermetic and avoid
unnecessary third‑party dependencies.
"""

from __future__ import annotations

import inspect

import asyncio
import typing as t


def serialize_component_info(component: t.Any) -> dict[str, t.Any]:
    """Return a simple, safe summary of a component.

    Includes type, module, public attributes and public methods. On failure,
    returns a minimal structure with an error description.
    """
    try:
        cls = component.__class__
        type_name = getattr(cls, "__name__", "Unknown")
        module_name = getattr(cls, "__module__", "Unknown")

        attributes: list[str] = []
        methods: list[str] = []

        for name in dir(component):
            if name.startswith("_"):
                continue
            try:
                value = getattr(component, name)
            except Exception:
                continue
            if inspect.ismethod(value) or inspect.isfunction(value) or callable(value):
                methods.append(name)
            else:
                attributes.append(name)

        return {
            "type": type_name,
            "module": module_name,
            "attributes": attributes,
            "methods": methods,
        }
    except Exception as e:  # pragma: no cover - defensive path
        return {"type": "Unknown", "module": "Unknown", "error": str(e)}


def format_tool_response(response: t.Any) -> dict[str, t.Any]:
    """Normalize tool responses into a consistent dict shape.

    - dict -> dict
    - list/tuple -> {"items": [...]}
    - primitives/other -> {"value": value or str(value)}
    """
    if isinstance(response, dict):
        return response
    if isinstance(response, (list, tuple)):
        return {"items": list(response)}
    if isinstance(response, (str, int, float, bool)) or response is None:
        return {"value": response}
    return {"value": str(response)}


def validate_parameters(parameters: dict[str, t.Any], required: list[str]) -> bool:
    """Return True if all required parameter keys are present (and not None)."""
    for key in required:
        if key not in parameters or parameters[key] is None:
            return False
    return True


def get_parameter(
    parameters: dict[str, t.Any],
    key: str,
    default: t.Any | None = None,
) -> t.Any:
    """Fetch a parameter from a dictionary with an optional default."""
    return parameters.get(key, default)


async def async_retry(
    func: t.Callable[..., t.Awaitable[t.Any]],
    max_attempts: int,
    delay: float,
    *args: t.Any,
    **kwargs: t.Any,
) -> t.Any:
    """Retry an async function up to max_attempts with a fixed delay.

    Raises the last exception if all attempts fail.
    """
    attempt = 0
    last_exc: BaseException | None = None
    while attempt < max_attempts:
        try:
            return await func(*args, **kwargs)
        except BaseException as e:  # noqa: BLE001 - re-raised after retries
            last_exc = e
            attempt += 1
            if attempt >= max_attempts:
                break
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
