"""Shared building blocks for all versioned data contracts.

Versioning rule (semver on SCHEMA_VERSION):
- patch: documentation / validation fixes, no shape change
- minor: new optional fields or new enum members (old readers keep working)
- major: removed/renamed fields or changed meaning; old files need migration
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.11.0"

# Job ids are uuid4 hex strings.
JOB_ID_PATTERN = r"^[0-9a-f]{32}$"


class Contract(BaseModel):
    """Base for every contract model: unknown fields are rejected."""

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=False,
        # Fields with defaults are always present in serialized output,
        # so the generated TypeScript types mark them as required.
        json_schema_serialization_defaults_required=True,
    )


class VersionedContract(Contract):
    """Top-level documents (API responses, files on disk) carry a schema version."""

    schema_version: str = Field(
        default=SCHEMA_VERSION,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Semantic version of the contract this document follows.",
    )


class DataOrigin(StrEnum):
    """Where analysis values come from. Demo data must never be shown as measured."""

    measured = "measured"
    demo = "demo"


def utcnow() -> datetime:
    return datetime.now(UTC)
