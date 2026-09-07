from pydantic import BaseModel, ConfigDict, Field

from .enums import AttemptState, FormalRunState


class AttemptTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_state: AttemptState
    target_state: AttemptState
    is_formal: bool
    expected_resource_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=128)
    request_id: str = Field(min_length=8, max_length=128)


class FormalRunTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_state: FormalRunState
    target_state: FormalRunState
    expected_resource_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=128)
    request_id: str = Field(min_length=8, max_length=128)


class TransitionValidationResponse(BaseModel):
    valid: bool
    machine: str
    current_state: str
    target_state: str
