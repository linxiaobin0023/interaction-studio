from dataclasses import dataclass
from enum import StrEnum

from .enums import AttemptState, FormalRunState


@dataclass(frozen=True)
class InvalidTransition[StateT: StrEnum](ValueError):
    machine: str
    current: StateT
    target: StateT
    allowed: frozenset[StateT]

    def __str__(self) -> str:
        allowed = ", ".join(sorted(state.value for state in self.allowed)) or "none"
        return (
            f"invalid {self.machine} transition {self.current.value} -> "
            f"{self.target.value}; allowed: {allowed}"
        )


ATTEMPT_TRANSITIONS: dict[AttemptState, frozenset[AttemptState]] = {
    AttemptState.CREATED: frozenset({AttemptState.PREPARED, AttemptState.CANCELLED}),
    AttemptState.PREPARED: frozenset(
        {AttemptState.INFERENCE_STARTED, AttemptState.SYSTEM_FAIL, AttemptState.CANCELLED}
    ),
    AttemptState.INFERENCE_STARTED: frozenset(
        {AttemptState.INFERENCE_SUCCEEDED, AttemptState.RETRY_PENDING, AttemptState.SYSTEM_FAIL}
    ),
    AttemptState.RETRY_PENDING: frozenset(
        {AttemptState.INFERENCE_STARTED, AttemptState.SYSTEM_FAIL}
    ),
    AttemptState.INFERENCE_SUCCEEDED: frozenset(
        {AttemptState.OUTPUT_PERSISTED, AttemptState.OUTPUT_VALIDATION_FAILED}
    ),
    AttemptState.OUTPUT_PERSISTED: frozenset({AttemptState.OUTPUT_VALIDATING}),
    AttemptState.OUTPUT_VALIDATING: frozenset(
        {AttemptState.VALID_OUTPUT, AttemptState.OUTPUT_VALIDATION_FAILED}
    ),
    AttemptState.OUTPUT_VALIDATION_FAILED: frozenset(
        {AttemptState.RETRY_PENDING, AttemptState.SYSTEM_FAIL}
    ),
    AttemptState.VALID_OUTPUT: frozenset(),
    AttemptState.SYSTEM_FAIL: frozenset(),
    AttemptState.CANCELLED: frozenset(),
}

FORMAL_RUN_TRANSITIONS: dict[FormalRunState, frozenset[FormalRunState]] = {
    FormalRunState.DRAFT: frozenset({FormalRunState.READY, FormalRunState.INVALIDATED}),
    FormalRunState.READY: frozenset({FormalRunState.RUNNING, FormalRunState.INVALIDATED}),
    FormalRunState.RUNNING: frozenset(
        {FormalRunState.REVIEW_PENDING, FormalRunState.INVALIDATED}
    ),
    FormalRunState.REVIEW_PENDING: frozenset(
        {FormalRunState.COMPLETED, FormalRunState.INVALIDATED}
    ),
    FormalRunState.COMPLETED: frozenset(),
    FormalRunState.INVALIDATED: frozenset(),
}


def require_transition[StateT: StrEnum](
    machine: str,
    current: StateT,
    target: StateT,
    transitions: dict[StateT, frozenset[StateT]],
) -> None:
    allowed = transitions[current]
    if target not in allowed:
        raise InvalidTransition(machine, current, target, allowed)


def require_attempt_transition(
    current: AttemptState,
    target: AttemptState,
    *,
    is_formal: bool,
) -> None:
    allowed = ATTEMPT_TRANSITIONS[current]
    if is_formal and target is AttemptState.CANCELLED:
        raise InvalidTransition("attempt", current, target, frozenset(allowed - {target}))
    require_transition("attempt", current, target, ATTEMPT_TRANSITIONS)


def require_formal_run_transition(current: FormalRunState, target: FormalRunState) -> None:
    require_transition("formal_run", current, target, FORMAL_RUN_TRANSITIONS)


def serialize_transitions[StateT: StrEnum](
    transitions: dict[StateT, frozenset[StateT]],
) -> dict[str, list[str]]:
    return {
        current.value: sorted(target.value for target in targets)
        for current, targets in transitions.items()
    }
