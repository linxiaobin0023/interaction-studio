from fastapi import APIRouter

from ..domain.readiness import (
    ReadinessEvaluationRequest,
    ReadinessEvaluationResponse,
    evaluate_readiness,
)

router = APIRouter(prefix="/api/v1/readiness", tags=["readiness"])


@router.post(
    "/evaluations",
    response_model=ReadinessEvaluationResponse,
    operation_id="evaluateReadinessManifest",
)
def create_readiness_evaluation(
    request: ReadinessEvaluationRequest,
) -> ReadinessEvaluationResponse:
    return evaluate_readiness(request)
