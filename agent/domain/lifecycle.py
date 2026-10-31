"""
Lifecycle state machine for Paytm Saathi.

Defines legal state transitions and which actions are allowed in each state.
The planner may NEVER return an action outside the allowed set for the current state.
"""
from typing import FrozenSet

from agent.domain.enums import ActionType, LifecycleState

# ─────────────────────────────────────────────
# Legal transitions: (from_state, to_state)
# ─────────────────────────────────────────────
_LEGAL_TRANSITIONS: set[tuple[LifecycleState, LifecycleState]] = {
    (LifecycleState.NEW, LifecycleState.CONTACTED),
    (LifecycleState.NEW, LifecycleState.ENGAGED),          # merchant messaged first
    (LifecycleState.CONTACTED, LifecycleState.ENGAGED),
    (LifecycleState.CONTACTED, LifecycleState.DORMANT),
    (LifecycleState.ENGAGED, LifecycleState.DOCS_PENDING),
    (LifecycleState.ENGAGED, LifecycleState.LOST),
    (LifecycleState.DOCS_PENDING, LifecycleState.DOCS_VERIFIED),
    (LifecycleState.DOCS_PENDING, LifecycleState.DORMANT),
    (LifecycleState.DOCS_VERIFIED, LifecycleState.VISIT_SCHEDULED),
    (LifecycleState.VISIT_SCHEDULED, LifecycleState.INSTALLED),
    (LifecycleState.INSTALLED, LifecycleState.ACTIVATING),
    (LifecycleState.INSTALLED, LifecycleState.AT_RISK),
    (LifecycleState.ACTIVATING, LifecycleState.ACTIVATED),
    (LifecycleState.ACTIVATING, LifecycleState.AT_RISK),
    (LifecycleState.AT_RISK, LifecycleState.ACTIVATING),
    (LifecycleState.DORMANT, LifecycleState.CONTACTED),    # after cooldown
}

# ─────────────────────────────────────────────
# Allowed actions per state
# ─────────────────────────────────────────────
_ALLOWED_ACTIONS: dict[LifecycleState, FrozenSet[ActionType]] = {
    LifecycleState.NEW: frozenset({
        ActionType.SEND_INTRO,
        ActionType.WAIT,
        ActionType.CLOSE_LEAD,
        ActionType.ANSWER_QUERY,   # when merchant messaged first
        ActionType.ESCALATE,
    }),
    LifecycleState.CONTACTED: frozenset({
        ActionType.SEND_INTRO,     # retry
        ActionType.ANSWER_QUERY,
        ActionType.WAIT,
        ActionType.ESCALATE,
    }),
    LifecycleState.ENGAGED: frozenset({
        ActionType.ANSWER_QUERY,
        ActionType.REQUEST_DOCS,
        ActionType.SCHEDULE_VISIT,
        ActionType.ESCALATE,
        ActionType.CLOSE_LEAD,
        ActionType.OFFER_DISCOUNT,
    }),
    LifecycleState.DOCS_PENDING: frozenset({
        ActionType.REQUEST_DOCS,
        ActionType.REREQUEST_DOC,
        ActionType.ANSWER_QUERY,
        ActionType.WAIT,
        ActionType.ESCALATE,
    }),
    LifecycleState.DOCS_VERIFIED: frozenset({
        ActionType.SCHEDULE_VISIT,
        ActionType.ESCALATE,
    }),
    LifecycleState.VISIT_SCHEDULED: frozenset({
        ActionType.WAIT,
        ActionType.ANSWER_QUERY,
        ActionType.ESCALATE,
    }),
    LifecycleState.INSTALLED: frozenset({
        ActionType.SEND_ACTIVATION_NUDGE,
        ActionType.ANSWER_QUERY,
        ActionType.EXPLAIN_SETTLEMENT,
        ActionType.WAIT,
        ActionType.ESCALATE,
    }),
    LifecycleState.ACTIVATING: frozenset({
        ActionType.SEND_ACTIVATION_NUDGE,
        ActionType.ANSWER_QUERY,
        ActionType.EXPLAIN_SETTLEMENT,
        ActionType.WAIT,
        ActionType.ESCALATE,
    }),
    LifecycleState.AT_RISK: frozenset({
        ActionType.ESCALATE,
        ActionType.SEND_ACTIVATION_NUDGE,
    }),
    LifecycleState.ACTIVATED: frozenset({
        ActionType.EXPLAIN_SETTLEMENT,
        ActionType.ANSWER_QUERY,
        ActionType.ESCALATE,
        ActionType.WAIT,
    }),
    LifecycleState.DORMANT: frozenset({
        ActionType.WAIT,
        ActionType.SEND_INTRO,   # after cooldown
        ActionType.ESCALATE,
    }),
    LifecycleState.LOST: frozenset({
        ActionType.WAIT,
    }),
}


def allowed_actions(state: LifecycleState) -> FrozenSet[ActionType]:
    """Return the frozenset of actions permitted in the given lifecycle state."""
    return _ALLOWED_ACTIONS.get(state, frozenset({ActionType.WAIT}))


def is_legal_transition(from_state: LifecycleState, to_state: LifecycleState) -> bool:
    """Return True if transitioning from_state → to_state is legal."""
    return (from_state, to_state) in _LEGAL_TRANSITIONS
