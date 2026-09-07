import pytest

from interaction_studio_api.domain.enums import AttemptState, FormalRunState
from interaction_studio_api.domain.state_machines import (
    InvalidTransition,
    require_attempt_transition,
    require_formal_run_transition,
)


def test_attempt_happy_path() -> None:
    states = [
        AttemptState.CREATED,
        AttemptState.PREPARED,
        AttemptState.INFERENCE_STARTED,
        AttemptState.INFERENCE_SUCCEEDED,
        AttemptState.OUTPUT_PERSISTED,
        AttemptState.OUTPUT_VALIDATING,
        AttemptState.VALID_OUTPUT,
    ]

    for current, target in zip(states, states[1:], strict=False):
        require_attempt_transition(current, target, is_formal=True)


def test_formal_attempt_cannot_be_cancelled() -> None:
    with pytest.raises(InvalidTransition):
        require_attempt_transition(
            AttemptState.CREATED,
            AttemptState.CANCELLED,
            is_formal=True,
        )


def test_non_formal_attempt_can_be_cancelled_before_inference() -> None:
    require_attempt_transition(
        AttemptState.PREPARED,
        AttemptState.CANCELLED,
        is_formal=False,
    )


def test_terminal_attempt_cannot_be_reopened() -> None:
    with pytest.raises(InvalidTransition):
        require_attempt_transition(
            AttemptState.VALID_OUTPUT,
            AttemptState.PREPARED,
            is_formal=False,
        )


def test_completed_formal_run_is_immutable() -> None:
    with pytest.raises(InvalidTransition):
        require_formal_run_transition(FormalRunState.COMPLETED, FormalRunState.RUNNING)


def test_formal_run_happy_path() -> None:
    states = [
        FormalRunState.DRAFT,
        FormalRunState.READY,
        FormalRunState.RUNNING,
        FormalRunState.REVIEW_PENDING,
        FormalRunState.COMPLETED,
    ]

    for current, target in zip(states, states[1:], strict=False):
        require_formal_run_transition(current, target)
