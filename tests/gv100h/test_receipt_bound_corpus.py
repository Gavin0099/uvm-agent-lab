"""Public pins and synthetic fail-closed cases; no Git, Gold or private payloads."""
import hashlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk
from gv100h.spec_qa.frozen_corpus import receipt_bound_corpus as rbc

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "gv100h/spec_qa/frozen_corpus/s56c_pdf_ingestion.py"
# Fixed characterization from the unchanged main retriever, not computed with
# the new receipt loader while the test runs. Source content is synthetic.
SYNTHETIC_IDENTITY = "7e878c2283f22570d1adf695892c4bf427a3272cdaf17614aa19d1f0f92b9a22"
SYNTHETIC_CORPUS = "43097b4010961333fa97bde358fc7bcef0bae7ccf4a72cd6d595abd005613332"


def synthetic_chunk(index=0):
    return GovernedChunk.build(source_id="usb20_fw", document="Synthetic manual", revision="1",
        section="3.1", page_or_anchor="p.1", authority_level="authoritative",
        chunk_kind="paragraph", content="alpha beta", index=index)


def fixture_pins(monkeypatch):
    monkeypatch.setattr(rbc, "PINNED_CHUNK_COUNT", 1)
    monkeypatch.setattr(rbc, "PINNED_CHUNK_IDENTITY_SHA256", SYNTHETIC_IDENTITY)
    monkeypatch.setattr(rbc, "PINNED_CORPUS_SHA256", SYNTHETIC_CORPUS)


def test_loader_pins_match_the_sanitized_archived_identity_and_source_bytes():
    identity = json.loads((ROOT / "contracts/spec_qa_frozen_corpus_s56c_identity.json").read_text())
    assert rbc.PINNED_CHUNK_COUNT == identity["corpus_chunk_count"] == 4330
    assert rbc.PINNED_CORPUS_SHA256 == identity["corpus_sha256"]
    assert rbc.PINNED_CHUNK_IDENTITY_SHA256 == identity["chunk_identity_sha256"]
    assert rbc.PINNED_INGESTION_SHA256 == identity["authoring_pdf_ingestion_sha256"] == hashlib.sha256(FROZEN.read_bytes()).hexdigest()
    assert rbc.PINNED_CORPUS_LOCK_SHA256 == identity["corpus_lock_sha256"] == hashlib.sha256(rbc.DEFAULT_LOCK_PATH.read_bytes()).hexdigest()
    assert list(rbc.PINNED_SOURCE_IDS) == identity["source_ids"]


def test_matching_synthetic_identity_returns_the_fixed_receipt_digest(monkeypatch):
    fixture_pins(monkeypatch)
    assert rbc.chunk_identity_sha256([synthetic_chunk()]) == SYNTHETIC_IDENTITY
    assert rbc._verify_corpus_identity([synthetic_chunk()]) == SYNTHETIC_CORPUS


@pytest.mark.parametrize("fault", ["count", "duplicate", "identity", "tokenization"])
def test_drift_is_rejected_at_the_correct_identity_layer(monkeypatch, fault):
    fixture_pins(monkeypatch)
    chunks = [synthetic_chunk()]
    expected = {"count": "chunk count", "duplicate": "not unique", "identity": "chunk identity SHA-256", "tokenization": "tokenization has drifted"}[fault]
    if fault == "count":
        monkeypatch.setattr(rbc, "PINNED_CHUNK_COUNT", 2)
    elif fault == "duplicate":
        chunks *= 2
        monkeypatch.setattr(rbc, "PINNED_CHUNK_COUNT", 2)
    elif fault == "identity":
        chunks = [synthetic_chunk(1)]
    else:
        monkeypatch.setattr(rbc, "PINNED_CORPUS_SHA256", "0" * 64)
    with pytest.raises(rbc.ReceiptBoundCorpusError, match=expected):
        rbc._verify_corpus_identity(chunks)


def test_changed_frozen_ingestion_fails_before_execution(tmp_path, monkeypatch):
    target = tmp_path / "changed.py"
    target.write_bytes(FROZEN.read_bytes() + b"\nraise AssertionError('not verified')\n")
    monkeypatch.setattr(rbc, "_FROZEN_INGESTION_PATH", target)
    with pytest.raises(rbc.ReceiptBoundCorpusError, match="frozen ingestion implementation"):
        rbc.load_receipt_bound_corpus(raw_root=tmp_path)


def test_poisoned_module_cache_is_not_executed(monkeypatch):
    poison = ModuleType(rbc._FROZEN_INGESTION_MODULE)
    poison.load_accepted_chunks = lambda *args, **kwargs: pytest.fail("cache must be ignored")
    monkeypatch.setitem(sys.modules, rbc._FROZEN_INGESTION_MODULE, poison)
    loaded = rbc._load_frozen_ingestion()
    assert loaded is not poison
    assert callable(loaded.chunk_pdf)
    assert sys.modules[rbc._FROZEN_INGESTION_MODULE] is poison


def test_changed_lock_is_rejected_before_any_pdf_read(tmp_path):
    target = tmp_path / "corpus.lock.yaml"
    target.write_bytes(rbc.DEFAULT_LOCK_PATH.read_bytes() + b"\n# changed\n")
    with pytest.raises(rbc.ReceiptBoundCorpusError, match="corpus lock"):
        rbc.load_receipt_bound_corpus(raw_root=tmp_path, lock_path=target)


def test_missing_pdf_and_wrong_pdf_bytes_fail_closed(tmp_path):
    with pytest.raises(rbc.ReceiptBoundCorpusError, match="does not exist"):
        rbc.load_receipt_bound_corpus(raw_root=tmp_path)
    target = tmp_path / "usb20/usb_20.pdf"
    target.parent.mkdir()
    target.write_bytes(b"%PDF-not-the-locked-document")
    with pytest.raises(rbc.ReceiptBoundCorpusError, match="content_sha256 mismatch"):
        rbc.load_receipt_bound_corpus(raw_root=tmp_path)


def test_verified_lock_bytes_are_the_bytes_given_to_ingestion(tmp_path, monkeypatch):
    fixture_pins(monkeypatch)
    target = tmp_path / "lock.yaml"
    original = b"sources: {}\nlabel: checked\n"
    target.write_bytes(original)
    monkeypatch.setattr(rbc, "PINNED_CORPUS_LOCK_SHA256", hashlib.sha256(original).hexdigest())
    captured = []
    def ingest(ids, lock, **kwargs):
        captured.append(lock)
        return [synthetic_chunk()]
    monkeypatch.setattr(rbc, "_load_frozen_ingestion", lambda: SimpleNamespace(load_accepted_chunks=ingest))
    read_bytes = Path.read_bytes
    def swap_after_read(path):
        data = read_bytes(path)
        if path == target:
            path.write_bytes(b"label: changed-after-verification\n")
        return data
    monkeypatch.setattr(Path, "read_bytes", swap_after_read)
    result = rbc.load_receipt_bound_corpus(raw_root=tmp_path, lock_path=target)
    assert captured == [{"sources": {}, "label": "checked"}]
    assert result.corpus_sha256 == SYNTHETIC_CORPUS
    assert result.chunk_identity_sha256 == SYNTHETIC_IDENTITY
    assert result.get_chunk(synthetic_chunk().chunk_id).content == "alpha beta"
    assert result.get_chunk("missing") is None
    assert target.read_text() == "label: changed-after-verification\n"
