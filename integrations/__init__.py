"""
Integrations package – connects Saathi to the outside world.

Exposes ``configure()`` which is called once by ``server/main.py`` at startup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from agent.ports import AgentResult, Clock, IncomingEvent

    from integrations.ports import Store

# Module-level references set by configure()
_store: Store | None = None
_on_incoming: Callable[[IncomingEvent], AgentResult] | None = None
_clock: Clock | None = None


def configure(
    store: Store,
    on_incoming: Callable[[IncomingEvent], AgentResult],
    clock: Clock,
) -> None:
    """Inject runtime dependencies.  Called once by ``server/main.py``."""
    global _store, _on_incoming, _clock
    _store = store
    _on_incoming = on_incoming
    _clock = clock

    # propagate to sub-modules that need them
    from integrations import router, simulator  # noqa: E402

    router.configure(store=store, clock=clock)
    simulator.configure(store=store, on_incoming=on_incoming, clock=clock)


def get_store() -> Store:
    assert _store is not None, "integrations.configure() not called"
    return _store


def get_on_incoming() -> Callable[[IncomingEvent], AgentResult]:
    assert _on_incoming is not None, "integrations.configure() not called"
    return _on_incoming


def get_clock() -> Clock:
    assert _clock is not None, "integrations.configure() not called"
    return _clock
