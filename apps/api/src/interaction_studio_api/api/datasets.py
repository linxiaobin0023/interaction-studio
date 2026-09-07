from fastapi import APIRouter, Depends, HTTPException

from ..config import Settings, get_settings
from ..domain.dataset_releases import DatasetReleaseSummary, ReleaseDataset, read_release

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.get("/{dataset}/release", response_model=DatasetReleaseSummary)
def dataset_release(
    dataset: ReleaseDataset, settings: Settings = Depends(get_settings),  # noqa: B008
) -> DatasetReleaseSummary:
    try:
        return read_release(settings.artifact_root, dataset)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=503, detail={"code": "DATASET_RELEASE_UNAVAILABLE"}
        ) from exc
