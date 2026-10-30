"""
agent/tools/base.py — Base tool definition and ToolResult wrapper.

Every tool is a typed function with Pydantic input and output, wrapped by base.py,
which validates input, catches errors, and returns ToolResult(ok, data, error).
The LLM never calls tools directly.
"""
from __future__ import annotations

from typing import Any, Callable
from pydantic import BaseModel


class ToolResult(BaseModel):
    ok: bool
    data: dict[str, Any] = {}
    error: str | None = None


def wrap_tool(fn: Callable[..., Any]) -> Callable[..., ToolResult]:
    def wrapper(*args: Any, **kwargs: Any) -> ToolResult:
        try:
            res = fn(*args, **kwargs)
            if isinstance(res, BaseModel):
                data = res.model_dump()
            elif isinstance(res, dict):
                data = res
            else:
                data = {"result": res}
            return ToolResult(ok=True, data=data)
        except Exception as e:
            return ToolResult(ok=False, error=str(e))
    return wrapper

