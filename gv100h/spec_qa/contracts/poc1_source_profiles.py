"""Versioned source profiles for POC-1 acceptance benchmarks.

The v1 profile preserves the legacy five-source whole-Phase-1 contract. The v2 PDF-only
profile is an explicit benchmark choice; it does not remove hub_reference from
the repository corpus lock or from the legacy whole-corpus binding contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class POC1SourceProfileError(ValueError):
    """A manifest selects an unknown or schema-incompatible source profile."""


POC1_V1_SOURCE_PROFILE_ID = "poc1_v1_full_phase1"
POC1_V2_PDF_SOURCE_PROFILE_ID = "poc1_v2_official_pdf_only"


@dataclass(frozen=True)
class POC1SourceProfile:
    profile_id: str
    manifest_schema_version: str
    required_source_ids: tuple[str, ...]
    binding_mode: str


POC1_SOURCE_PROFILES = {
    POC1_V1_SOURCE_PROFILE_ID: POC1SourceProfile(
        profile_id=POC1_V1_SOURCE_PROFILE_ID,
        manifest_schema_version="1.1",
        required_source_ids=(
            "hub_reference",
            "usb20_fw",
            "usb20_se",
            "usb32",
            "superspeed_hub_lvs",
        ),
        binding_mode="whole_phase1_corpus",
    ),
    POC1_V2_PDF_SOURCE_PROFILE_ID: POC1SourceProfile(
        profile_id=POC1_V2_PDF_SOURCE_PROFILE_ID,
        manifest_schema_version="1.2",
        required_source_ids=(
            "usb20_fw",
            "usb20_se",
            "usb32",
            "superspeed_hub_lvs",
        ),
        binding_mode="receipt_bound_official_pdf_corpus",
    ),
}


def resolve_poc1_source_profile(
    *, schema_version: str, source_profile_id: Optional[str]
) -> POC1SourceProfile:
    """Resolve the benchmark's exact source profile without changing v1 defaults."""
    if schema_version == "1.1":
        if source_profile_id not in (None, POC1_V1_SOURCE_PROFILE_ID):
            raise POC1SourceProfileError(
                "schema 1.1 acceptance manifests use the legacy five-source profile"
            )
        return POC1_SOURCE_PROFILES[POC1_V1_SOURCE_PROFILE_ID]

    if schema_version == "1.2":
        if source_profile_id is None:
            raise POC1SourceProfileError(
                "schema 1.2 acceptance manifests must declare source_profile_id"
            )
        profile = POC1_SOURCE_PROFILES.get(source_profile_id)
        if profile is None or profile.manifest_schema_version != schema_version:
            raise POC1SourceProfileError(
                f"source_profile_id {source_profile_id!r} is not registered for schema 1.2"
            )
        return profile

    raise POC1SourceProfileError(
        f"no POC-1 source profile is registered for schema {schema_version!r}"
    )
