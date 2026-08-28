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
KNOWN_RETRIEVAL_MODES: Tuple[str, ...] = ("single_scope", "explicit_cross_scope")


class RetrievalPolicyError(ValueError):
    """Raised when a RetrievalPolicy's fields are internally inconsistent."""


def validate_policy_inputs(
    *,
    domain: str,
    retrieval_mode: RetrievalMode,
    allowed_evidence_scopes: Optional[Tuple[str, ...]],
) -> None:
    """
    Validate the domain/retrieval_mode/allowed_evidence_scopes combination
    independent of answer_scope.

    RetrievalPolicy itself cannot be constructed without an answer_scope
    (it is a required field), which previously meant a caller could skip
    *all* policy validation -- including an unknown domain, an unknown
    retrieval_mode, or a retrieval_mode="explicit_cross_scope" declaration
    missing allowed_evidence_scopes -- simply by omitting answer_scope
    (Codex review, PR #33, P2). This function covers exactly the subset of
    RetrievalPolicy's validation that does not depend on answer_scope, so
    callers (qa_service.py's answer_question()) can run it unconditionally,
    before any answer_scope-gated construction of RetrievalPolicy itself.

    ``retrieval_mode``'s ``RetrievalMode`` type annotation is a
    ``typing.Literal`` -- Python does not enforce that at runtime for a
    plain function parameter, only pydantic's model validation does. When
    answer_scope is omitted, RetrievalPolicy is never constructed, so an
    invalid runtime value (e.g. retrieval_mode="bogus") would previously
    reach only the `== "explicit_cross_scope"` branch below, silently pass,
    and never be rejected (Codex review, PR #33, fresh finding on
    edf8825). Membership must therefore be checked explicitly here too.
    """
    if domain not in KNOWN_DOMAINS:
        raise RetrievalPolicyError(
            f"unknown retrieval domain {domain!r}; expected one of {KNOWN_DOMAINS}"
        )
    if retrieval_mode not in KNOWN_RETRIEVAL_MODES:
        raise RetrievalPolicyError(
            f"unknown retrieval_mode {retrieval_mode!r}; expected one of "
            f"{KNOWN_RETRIEVAL_MODES}"
        )
    if retrieval_mode == "explicit_cross_scope" and not allowed_evidence_scopes:
        raise RetrievalPolicyError(
            "explicit_cross_scope retrieval_mode requires a non-empty "
            "allowed_evidence_scopes; the retriever will not infer cross-scope "
            "evidence scopes on its own."
        )


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
        validate_policy_inputs(
            domain=self.domain,
            retrieval_mode=self.retrieval_mode,
            allowed_evidence_scopes=self.allowed_evidence_scopes,
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

        return self
