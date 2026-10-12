"""Answer-independent structure for the existing Typed Claim wire envelope.

Callers explicitly bind schema, question and the citation IDs actually supplied
in their request. This layer checks structure and ID membership only. It does
not load benchmark mappings, require particular answers, resolve source bytes,
judge citation support or validate localized display meaning.

Question-specific value schemas and evaluators belong to separate adapters.
Existing benchmark DTOs and the default QA path are deliberately unchanged.
"""
from __future__ import annotations

import json
from collections.abc import Collection
from typing import Annotated

from pydantic import (
    BaseModel, ConfigDict, Field, JsonValue, StringConstraints, TypeAdapter,
    ValidationError, field_validator, model_serializer, model_validator,
)


class TypedClaimStructureError(ValueError):
    """The wire structure or its explicitly supplied request binding is invalid."""


CitationId = Annotated[str, StringConstraints(
    pattern=r"^[^:\s]+:[^:\s]+:[^:\s]+:(0|[1-9][0-9]*):[0-9a-f]{64}$",
)]
_CITATION_ID = TypeAdapter(CitationId)


class TypedClaimDisplayText(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    locale: str = Field(min_length=2, pattern=r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
    text: str = Field(min_length=1)

    @field_validator("locale", "text")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("display text fields must not be blank")
        return value


class TypedClaimStructureRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claim_id: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    value: JsonValue
    citation_ids: list[CitationId] = Field(min_length=1, json_schema_extra={"uniqueItems": True},
        description="Unique IDs from response_citation_ids; membership is not semantic support.")
    display_text: TypedClaimDisplayText

    @field_validator("claim_id", "relation")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim identity and relation must not be blank")
        return value

    @field_validator("value")
    @classmethod
    def finite_json_value(cls, value: JsonValue) -> JsonValue:
        # JsonValue alone permits non-finite floats when built from Python data.
        json.dumps(value, allow_nan=False)
        return value

    @field_validator("citation_ids")
    @classmethod
    def unique_citations(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("claim citation_ids must not contain duplicates")
        return value


class TypedClaimStructurePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: str = Field(alias="schema", min_length=1)
    question_id: str = Field(min_length=1, description="Echo the question identity supplied by the request.")
    response_citation_ids: list[CitationId] = Field(min_length=1, json_schema_extra={"uniqueItems": True},
        description="Unique citation IDs drawn only from the evidence supplied in this request.")
    claims: list[TypedClaimStructureRecord] = Field(min_length=1,
        description="Every claim_id must be unique. Value and relation semantics are checked by separate adapters.")

    @field_validator("schema_version", "question_id")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("schema and question identity must not be blank")
        return value

    @model_serializer(mode="wrap")
    def schema_alias(self, handler):
        payload = handler(self)
        if "schema_version" in payload:
            payload["schema"] = payload.pop("schema_version")
        return payload

    @model_validator(mode="after")
    def unique_identity_and_citation_membership(self) -> "TypedClaimStructurePayload":
        if len(self.response_citation_ids) != len(set(self.response_citation_ids)):
            raise ValueError("response citation IDs must be unique")
        identities = [claim.claim_id for claim in self.claims]
        if len(identities) != len(set(identities)):
            raise ValueError("claim IDs must be unique")
        response_ids = set(self.response_citation_ids)
        if any(set(claim.citation_ids) - response_ids for claim in self.claims):
            raise ValueError("claim citation absent from response_citation_ids")
        return self


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TypedClaimStructureError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value):
    raise TypedClaimStructureError(f"non-JSON numeric constant: {value}")


def parse_typed_claim_structure(
    raw: str, *, schema_version: str, question_id: str,
    prompt_citation_ids: Collection[str],
) -> TypedClaimStructurePayload:
    """Parse one strict JSON answer using explicit, request-local identities.

    The allowed IDs must come from the actual request, not an answer mapping.
    A shape pass never establishes required-claim coverage or answer correctness.
    Refusals use their own contract and are not accepted as answer envelopes.
    """
    if not isinstance(raw, str):
        raise TypedClaimStructureError("completion must be JSON text")
    if not all(isinstance(v, str) and v.strip() for v in (schema_version, question_id)):
        raise TypedClaimStructureError("expected schema and question must be explicit")
    if (isinstance(prompt_citation_ids, (str, bytes))
            or not isinstance(prompt_citation_ids, Collection) or not prompt_citation_ids):
        raise TypedClaimStructureError("prompt citation IDs must be a non-empty collection")
    try:
        allowed = [_CITATION_ID.validate_python(cid, strict=True) for cid in prompt_citation_ids]
        if len(allowed) != len(set(allowed)):
            raise TypedClaimStructureError("prompt citation IDs must be unique")
        decoded = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        payload = TypedClaimStructurePayload.model_validate(decoded)
    except (ValidationError, json.JSONDecodeError, ValueError) as exc:
        raise TypedClaimStructureError(str(exc)) from exc
    if payload.schema_version != schema_version or payload.question_id != question_id:
        raise TypedClaimStructureError("payload schema/question differs from request")
    if set(payload.response_citation_ids) - set(allowed):
        raise TypedClaimStructureError("response citation absent from prompt evidence")
    return payload


def typed_claim_structure_schema(*, schema_version: str) -> dict:
    """Public shape with a caller-selected version; never an answer-value enum."""
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise TypedClaimStructureError("schema version must be explicit")
    schema = TypedClaimStructurePayload.model_json_schema(by_alias=True)
    schema["properties"]["schema"]["const"] = schema_version
    return schema
