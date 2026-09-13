"""In-memory microgrid state snapshots for a single simulation run."""

from backend.common.exceptions import SimulationError
from backend.common.schemas.microgrid_state import MicrogridState


class MicrogridStateManager:
    """Maintains immutable-style snapshots without altering shared schemas."""

    def __init__(self) -> None:
        self._current: MicrogridState | None = None
        self._history: list[MicrogridState] = []

    def set_state(self, state: MicrogridState) -> MicrogridState:
        """Store a deep snapshot and return an independent copy to the caller."""
        snapshot = state.model_copy(deep=True)
        self._current = snapshot
        self._history.append(snapshot)
        return snapshot.model_copy(deep=True)

    def get_current(self) -> MicrogridState:
        if self._current is None:
            raise SimulationError("Simulation has not been initialized")
        return self._current.model_copy(deep=True)

    def get_history(self) -> list[MicrogridState]:
        return [state.model_copy(deep=True) for state in self._history]

    def clear(self) -> None:
        self._current = None
        self._history.clear()
