import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import AssetType, DatasetKind, ReadinessStatus

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ManifestAsset(BaseModel):
    model_config = ConfigDict(extra="allow")

    asset_id: str = Field(min_length=1, max_length=128)
    type: AssetType
    path: str = Field(min_length=1, max_length=512)
    sha256: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_identity_fields(self) -> "ManifestAsset":
        if not SHA256_RE.fullmatch(self.sha256):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")

        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("asset path must be relative and cannot traverse parents")
        return self


class AssetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: str
    pack_id: str
    created_at: datetime
    dataset: DatasetKind
    provenance: str
    model_revision: str
    formal_eligible: bool
    readiness_status: ReadinessStatus
    character_id: str
    product_sku: str
    assets: list[ManifestAsset] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_uniqueness_and_scope(self) -> "AssetManifest":
        asset_ids = [asset.asset_id for asset in self.assets]
        paths = [asset.path for asset in self.assets]
        if len(set(asset_ids)) != len(asset_ids):
            raise ValueError("asset_id values must be unique")
        if len(set(paths)) != len(paths):
            raise ValueError("asset paths must be unique")
        if self.provenance == "SYNTHETIC_MOCK" and (
            self.formal_eligible or self.dataset is DatasetKind.FORMAL
        ):
            raise ValueError("SYNTHETIC_MOCK assets cannot enter the Formal dataset")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone offset")
        return self

    def summary(self) -> dict[str, Any]:
        counts = {asset_type.value: 0 for asset_type in AssetType}
        for asset in self.assets:
            counts[asset.type.value] += 1
        return {
            "pack_id": self.pack_id,
            "dataset": self.dataset.value,
            "formal_eligible": self.formal_eligible,
            "readiness_status": self.readiness_status.value,
            "asset_count": len(self.assets),
            "counts_by_type": counts,
        }
