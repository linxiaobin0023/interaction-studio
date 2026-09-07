from fastapi import APIRouter

from ..domain.contracts import (
    AttemptTransitionRequest,
    FormalRunTransitionRequest,
    TransitionValidationResponse,
)
from ..domain.resources import CoreResourceContractBundle
from ..domain.state_machines import (
    ATTEMPT_TRANSITIONS,
    FORMAL_RUN_TRANSITIONS,
    require_attempt_transition,
    require_formal_run_transition,
    serialize_transitions,
)

router = APIRouter(prefix="/api/v1/contracts", tags=["contracts"])


@router.get(
    "/core-resources",
    response_model=CoreResourceContractBundle,
    operation_id="getCoreResourceContracts",
)
def get_core_resource_contracts() -> CoreResourceContractBundle:
    return CoreResourceContractBundle(schema_version="0.1.0")


@router.get("/state-machines", operation_id="getStateMachineContracts")
def get_state_machines() -> dict[str, dict[str, list[str]]]:
    return {
        "attempt": serialize_transitions(ATTEMPT_TRANSITIONS),
        "formal_run": serialize_transitions(FORMAL_RUN_TRANSITIONS),
    }


@router.post(
    "/attempt-transitions/validate",
    response_model=TransitionValidationResponse,
    operation_id="validateAttemptTransition",
)
def validate_attempt_transition(
    request: AttemptTransitionRequest,
) -> TransitionValidationResponse:
    require_attempt_transition(
        request.current_state,
        request.target_state,
        is_formal=request.is_formal,
    )
    return TransitionValidationResponse(
        valid=True,
        machine="attempt",
        current_state=request.current_state.value,
        target_state=request.target_state.value,
    )


@router.post(
    "/formal-run-transitions/validate",
    response_model=TransitionValidationResponse,
    operation_id="validateFormalRunTransition",
)
def validate_formal_run_transition(
    request: FormalRunTransitionRequest,
) -> TransitionValidationResponse:
    require_formal_run_transition(request.current_state, request.target_state)
    return TransitionValidationResponse(
        valid=True,
        machine="formal_run",
        current_state=request.current_state.value,
        target_state=request.target_state.value,
    )
