"""
Retrieval Policy contract for GovernedSpecRetriever.

This replaces the old single ``target_scope`` string parameter, which
conflated two different concerns:

1. What scope the *answer itself* is about (``answer_scope``).
2. Which evidence scopes are *allowed to be cited* to support that answer
   (``allowed_evidence_scopes``).

Design principle (do not violate elsewhere in this codebase): the retriever
must never guess, from query text, whether a question "needs" cross-scope
evidence. The caller is solely responsible for explicitly declaring
``retrieval_mode`` and (when required) ``allowed_evidence_scopes`` up front.
This keeps retrieval policy decisions separate from any future query-intent
classification / Query Normalizer work, which is deliberately out of scope
here.

``retrieval_mode`` has exactly two values:

- ``single_scope`` (default): the answer may only cite evidence whose
  ``scope`` equals ``answer_scope``. If ``allowed_evidence_scopes`` is not
  provided, it is derived automatically as ``(answer_scope,)``. If it *is*
  provided, it must equal exactly ``(answer_scope,)`` -- anything else is a
  contract error, not a silently-accepted override.
- ``explicit_cross_scope``: the caller has explicitly decided this answer
  needs evidence from one or more scopes beyond (or instead of)
  ``answer_scope`` (e.g. "is PORT_LINK_STATE supported in USB 2.0?" needs the
  USB_3_X evidence that defines PORT_LINK_STATE to correctly explain it does
  not apply to USB 2.0). ``allowed_evidence_scopes`` is required and must be
  non-empty; the retriever never infers it.

``domain`` exists so the contract does not need a breaking change when a
second corpus domain (e.g. HID, PD, TYPE_C) is introduced. It is validated
against a known-domain list but is not used for any routing yet -- Phase 1
only has one domain.
"""
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ValidationError, model_validator

RetrievalMode = Literal["single_scope", "explicit_cross_scope"]

KNOWN_DOMAINS: Tuple[str, ...] = ("USB_HUB",)


class RetrievalPolicyError(ValueError):
    """Raised when a RetrievalPolicy's fields are internally inconsistent."""


class RetrievalPolicy(BaseModel):
    domain: str = "USB_HUB"
    answer_scope: str
    retrieval_mode: RetrievalMode = "single_scope"
    allowed_evidence_scopes: Optional[Tuple[str, ...]] = None

    def __init__(self, **data):
        # pydantic v2 wraps every exception raised inside a model_validator
        # (including our own RetrievalPolicyError) into a generic
        # pydantic_core.ValidationError. RetrievalPolicy is meant to be a
        # simple caller-facing value contract, so re-surface a plain
        # RetrievalPolicyError instead of leaking a pydantic-specific
        # exception shape to every call site (governed_retriever.py,
        # qa_service.py, and tests) that constructs one.
        try:
            super().__init__(**data)
        except ValidationError as exc:
            messages = "; ".join(error["msg"] for error in exc.errors())
            raise RetrievalPolicyError(messages) from exc

    @model_validator(mode="after")
    def _validate_and_normalize(self) -> "RetrievalPolicy":
        if self.domain not in KNOWN_DOMAINS:
            raise RetrievalPolicyError(
                f"unknown retrieval domain {self.domain!r}; expected one of {KNOWN_DOMAINS}"
            )

        if self.retrieval_mode == "single_scope":
            if self.allowed_evidence_scopes is None:
                self.allowed_evidence_scopes = (self.answer_scope,)
            elif tuple(self.allowed_evidence_scopes) != (self.answer_scope,):
                raise RetrievalPolicyError(
                    "single_scope retrieval_mode requires allowed_evidence_scopes to be "
                    f"exactly ({self.answer_scope!r},) or omitted; got "
                    f"{tuple(self.allowed_evidence_scopes)!r}. Use "
                    "retrieval_mode='explicit_cross_scope' to request additional evidence "
                    "scopes explicitly."
                )
        elif self.retrieval_mode == "explicit_cross_scope":
            if not self.allowed_evidence_scopes:
                raise RetrievalPolicyError(
                    "explicit_cross_scope retrieval_mode requires a non-empty "
                    "allowed_evidence_scopes; the retriever will not infer cross-scope "
                    "evidence scopes on its own."
                )

        return self
