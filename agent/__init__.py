"""
agent/__init__.py — Top-level agent package interface.

Exports the configure function and the 6 main agent entrypoints.
"""
from agent.core.entrypoint import (
    approve_action,
    configure,
    handle_incoming,
    handle_timer,
    preview_next_action,
    reject_action,
    run_batch,
)

__all__ = [
    "configure",
    "handle_incoming",
    "handle_timer",
    "run_batch",
    "preview_next_action",
    "approve_action",
    "reject_action",
]

