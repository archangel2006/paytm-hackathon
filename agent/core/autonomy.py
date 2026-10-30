"""
agent/core/autonomy.py — Autonomy level resolution.

Reads the per-action-type autonomy level from the store and maps it to
a guardrail verdict.
"""
from __future__ import annotations

from agent.domain.enums import ActionStatus, ActionType, AutonomyLevel
from agent.ports import Store


def resolve(action_type: ActionType, store: Store) -> tuple[AutonomyLevel, ActionStatus]:
    """
    Look up the current autonomy level for an action type.

    Returns:
        (autonomy_level, status_to_set)
        - L1: (L1, proposed)        — show as suggestion only
        - L2: (L2, pending_approval) — wait for human approval
        - L3: (L3, proposed)        — will be executed immediately
    """
    level = store.get_autonomy_level(action_type)
    if level == AutonomyLevel.L1:
        return AutonomyLevel.L1, ActionStatus.PROPOSED
    if level == AutonomyLevel.L2:
        return AutonomyLevel.L2, ActionStatus.PENDING_APPROVAL
    return AutonomyLevel.L3, ActionStatus.PROPOSED

