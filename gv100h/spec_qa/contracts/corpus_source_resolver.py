"""Resolves ``env://`` corpus source locators to verified physical paths.

``corpus.lock.yaml`` declares each Phase 1 official-raw source (``usb20_fw``,
``usb20_se``, ``usb32``, ``superspeed_hub_lvs``) with a ``source_locator`` of
the form ``env://<ENV_VAR_NAME>/<relative/path/to/file>``. This module
resolves those locators against the actual runtime environment so that
callers do not have to hand-build a ``source_paths`` mapping for
``GovernedSpecRetriever`` themselves.

The governed reference source (``hub_reference``) uses a different
``repo://owner/name@commit`` locator and continues to be bound through
``GovernedSpecRetriever.verify_and_bind_knowledge_repo`` /
``knowledge_repo_path`` -- it is intentionally out of scope for this
resolver.

Every failure mode here is fail-closed: an unset or blank environment
variable, a missing relative path segment, a non-existent file, an
unsupported locator scheme, a resolved path that escapes its ``env://`` root
(via ``..`` traversal, an absolute path segment, or a symlink pointing
outside the root), and a SHA-256 mismatch against the corpus lock's
``content_sha256`` all raise ``CorpusSourceResolverError``. There is no
best-effort or partial-success path -- ``resolve_all`` either returns a
complete mapping of verified paths or raises with every failure listed.
``resolve_all``'s default source set is derived from the corpus contract's
own ``layer``/``phase``/``included`` fields (every required Phase 1
official-raw source), not from the ``source_locator`` scheme, so a required
source left pending, blank, or mis-typed still surfaces as a failure instead
of being silently skipped.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

ENV_LOCATOR_SCHEME = "env://"

# Mirrors GovernedSpecRetriever.PENDING_MARKERS plus the "excluded from
# Phase 1" marker used by the usb4 entry. Kept as an independent literal
# here (rather than imported) so this module has no runtime dependency on
# gv100h.spec_qa.retrieval.governed_retriever.
_PENDING_LOCATOR_MARKERS = ("PENDING_ACQUISITION", "NOT_BOUND", "NOT_APPLICABLE")

# The required-raw-source set for resolve_all()'s default is derived from
# these corpus-contract fields, NOT from the source_locator scheme. Deriving
# from the locator would silently drop a required source whose locator is
# still a pending marker, blank, or written with the wrong scheme -- exactly
# the sources that most need to surface as a failure. usb4 is excluded via
# `included: false` / `phase: phase_2`; hub_reference is excluded via its
# `governed_reference` layer (it is bound separately, via repo://).
_REQUIRED_SOURCE_LAYER = "official_raw"
_REQUIRED_SOURCE_PHASE = "phase_1"


class CorpusSourceResolverError(ValueError):
    """Raised when an env:// corpus source locator cannot be fail-closed resolved."""


class CorpusSourceResolver:
    """Resolves ``env://`` corpus source locators to verified filesystem paths.

    Parameters
    ----------
    corpus_lock:
        A parsed ``corpus.lock.yaml`` mapping (as returned by
        ``GovernedSpecRetriever._load_corpus_lock`` / ``.corpus_lock``).
    env:
        Optional environment mapping to resolve variables against. Defaults
        to ``os.environ``. Tests should inject an explicit mapping instead
        of mutating real process environment variables.
    """

    def __init__(
        self,
        corpus_lock: Mapping[str, Any],
        *,
        env: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._corpus_lock = corpus_lock
        self._env: Mapping[str, str] = env if env is not None else os.environ

    def resolve(self, source_id: str) -> Path:
        """Resolve a single source_id's env:// locator to a verified path.

        Raises ``CorpusSourceResolverError`` for every fail-closed condition:
        unknown source_id, missing/pending/unsupported locator, unset or
        blank environment variable, missing relative path, missing file, or
        a SHA-256 mismatch against the bound ``content_sha256``.
        """
        sources = self._corpus_lock.get("sources")
        if not isinstance(sources, dict) or source_id not in sources:
            raise CorpusSourceResolverError(
                f"corpus lock has no source entry for {source_id!r}"
            )
        source = sources[source_id]
        if not isinstance(source, dict):
            raise CorpusSourceResolverError(
                f"corpus lock source entry for {source_id!r} must be a mapping"
            )

        resolved_path = self._resolve_locator(source_id, source.get("source_locator"))
        self._verify_content_hash(source_id, source, resolved_path)
        return resolved_path

    def resolve_all(self, source_ids: Optional[Iterable[str]] = None) -> Dict[str, Path]:
        """Resolve multiple sources, fail-closed across the whole batch.

        If ``source_ids`` is omitted, resolves every *required* Phase 1
        official-raw source declared in the corpus lock -- i.e. every
        source whose ``layer`` is ``official_raw``, ``phase`` is
        ``phase_1``, and ``included`` is not explicitly ``False``. This is
        derived from the corpus contract's own fields, not from the
        ``source_locator`` scheme, so a required source with a pending,
        blank, or wrong-scheme locator still surfaces as a resolution
        failure instead of being silently skipped. ``hub_reference`` is
        excluded (different layer, bound separately via ``repo://``).

        Returns a complete ``{source_id: Path}`` mapping only if every
        requested source resolves and verifies successfully. If any source
        fails, raises a single ``CorpusSourceResolverError`` listing every
        failure instead of returning a partial result.
        """
        if source_ids is None:
            source_ids = self._required_source_ids()

        resolved: Dict[str, Path] = {}
        failures: list[str] = []
        for source_id in source_ids:
            try:
                resolved[source_id] = self.resolve(source_id)
            except CorpusSourceResolverError as exc:
                failures.append(f"{source_id}: {exc}")

        if failures:
            raise CorpusSourceResolverError(
                "corpus source resolution failed for one or more sources:\n"
                + "\n".join(failures)
            )
        return resolved

    def _required_source_ids(self) -> list[str]:
        sources = self._corpus_lock.get("sources") or {}
        required = []
        for candidate_id, source in sources.items():
            if not isinstance(source, dict):
                continue
            if source.get("layer") != _REQUIRED_SOURCE_LAYER:
                continue
            if source.get("phase") != _REQUIRED_SOURCE_PHASE:
                continue
            if source.get("included") is False:
                continue
            required.append(candidate_id)
        return required

    def _resolve_locator(self, source_id: str, locator: Any) -> Path:
        if not isinstance(locator, str) or not locator.strip():
            raise CorpusSourceResolverError(
                f"source {source_id!r} has no source_locator"
            )
        if locator in _PENDING_LOCATOR_MARKERS:
            raise CorpusSourceResolverError(
                f"source {source_id!r} source_locator is still {locator!r} (not acquired)"
            )
        if not locator.startswith(ENV_LOCATOR_SCHEME):
            raise CorpusSourceResolverError(
                f"source {source_id!r} locator {locator!r} is not an env:// locator"
            )

        remainder = locator[len(ENV_LOCATOR_SCHEME):]
        env_var_name, _sep, relative_path = remainder.partition("/")
        if not env_var_name:
            raise CorpusSourceResolverError(
                f"source {source_id!r} locator {locator!r} is missing an environment variable name"
            )
        if not relative_path or not relative_path.strip():
            raise CorpusSourceResolverError(
                f"source {source_id!r} locator {locator!r} is missing a relative file path"
            )

        env_value = self._env.get(env_var_name)
        if not env_value or not env_value.strip():
            raise CorpusSourceResolverError(
                f"source {source_id!r} requires environment variable "
                f"{env_var_name!r} to be set to a non-blank raw corpus root"
            )

        root = Path(env_value).resolve()
        if Path(relative_path).is_absolute():
            raise CorpusSourceResolverError(
                f"source {source_id!r} locator {locator!r} has an absolute relative "
                f"path segment, which is not allowed: {relative_path!r}"
            )

        resolved_path = (root / relative_path).resolve()
        try:
            resolved_path.relative_to(root)
        except ValueError:
            raise CorpusSourceResolverError(
                f"source {source_id!r} resolved path escapes its source root "
                f"{root}: {resolved_path}"
            ) from None

        if not resolved_path.is_file():
            raise CorpusSourceResolverError(
                f"source {source_id!r} resolved path does not exist or is not a file: "
                f"{resolved_path}"
            )
        return resolved_path

    def _verify_content_hash(
        self,
        source_id: str,
        source: Mapping[str, Any],
        resolved_path: Path,
    ) -> None:
        expected_hash = source.get("content_sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise CorpusSourceResolverError(
                f"source {source_id!r} has no bound content_sha256 to verify against"
            )
        observed_hash = hashlib.sha256(resolved_path.read_bytes()).hexdigest()
        if observed_hash.lower() != expected_hash.lower():
            raise CorpusSourceResolverError(
                f"source {source_id!r} content hash mismatch: "
                f"expected {expected_hash}, observed {observed_hash} ({resolved_path})"
            )
