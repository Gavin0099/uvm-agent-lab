import hashlib
import sys
from pathlib import Path

import pytest
from fpdf import FPDF

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.spec_qa.ingestion.pdf_ingestion import (
    PdfIngestionError,
    chunk_pdf,
    ingest_source_from_corpus_lock,
    is_source_eligible_as_answer_evidence,
    load_accepted_chunks,
    resolve_source_locator,
    search_chunks,
    verify_source_hash,
)

# Synthetic PDF layout (built with fpdf2, since real licensed USB-IF spec PDFs
# are not available in this sandbox):
#   page 1: stray pre-heading text (must be dropped), then section
#           "10.16.2.1" (heading + a wrapped paragraph), then section
#           "10.16.2.2" (heading + a bordered 3x3 table)
#   page 2: section "10.16.3" (heading + a short paragraph)
_PRETEXT = "Draft - Confidential - Do Not Distribute"
_PARAGRAPH_TEXT = (
    "In USB 3.x Hub specifications, PORT_POWER feature selector value is 8. "
    "Used with SetPortFeature to enable VBUS power to the downstream port."
)
_TABLE_ROWS = [
    ("Selector", "Value", "Notes"),
    ("PORT_POWER", "8", "Enables VBUS power"),
    ("PORT_LINK_STATE", "5", "Sets link state"),
]
_PAGE2_PARAGRAPH = "The hub depth field indicates the level of the hub in the topology."


def _build_synthetic_pdf(path: Path) -> None:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=11)

    pdf.add_page()
    pdf.multi_cell(0, 6, _PRETEXT)
    pdf.ln(4)
    pdf.multi_cell(0, 6, "10.16.2.1 Hub Class Feature Selectors")
    pdf.ln(4)
    pdf.multi_cell(0, 6, _PARAGRAPH_TEXT)
    pdf.ln(4)
    pdf.multi_cell(0, 6, "10.16.2.2 Port Link State Feature Selector")
    pdf.ln(4)
    col_widths = (60, 30, 60)
    for row in _TABLE_ROWS:
        for width, value in zip(col_widths, row):
            pdf.cell(width, 6, value, border=1)
        pdf.ln(6)

    pdf.add_page()
    pdf.multi_cell(0, 6, "10.16.3 Hub Depth")
    pdf.ln(4)
    pdf.multi_cell(0, 6, _PAGE2_PARAGRAPH)

    pdf.output(str(path))


@pytest.fixture()
def synthetic_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "usb32_synthetic.pdf"
    _build_synthetic_pdf(pdf_path)
    return pdf_path


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _chunk_pdf(pdf_path: Path, **overrides):
    kwargs = dict(
        source_id="usb32_synth",
        document="USB 3.2 Specification",
        revision="Rev 1.1",
        authority_level="authoritative",
        expected_sha256=_sha256_of(pdf_path),
    )
    kwargs.update(overrides)
    return chunk_pdf(pdf_path, **kwargs)


def test_chunk_pdf_is_deterministic(synthetic_pdf):
    first = _chunk_pdf(synthetic_pdf)
    second = _chunk_pdf(synthetic_pdf)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert [c.content_sha256 for c in first] == [c.content_sha256 for c in second]


def test_chunk_pdf_drops_text_before_first_heading(synthetic_pdf):
    chunks = _chunk_pdf(synthetic_pdf)
    assert all(_PRETEXT not in c.content for c in chunks)


def test_chunk_pdf_derives_sections_pages_and_kinds(synthetic_pdf):
    chunks = _chunk_pdf(synthetic_pdf)
    by_kind = {}
    for chunk in chunks:
        by_kind.setdefault(chunk.chunk_kind, []).append(chunk)

    heading_sections = {c.section for c in by_kind["heading_only"]}
    assert heading_sections == {"10.16.2.1", "10.16.2.2", "10.16.3"}

    paragraphs = by_kind["paragraph"]
    section_1_paragraph = next(c for c in paragraphs if c.section == "10.16.2.1")
    assert "PORT_POWER feature selector value is 8" in section_1_paragraph.content
    assert "enable VBUS power" in section_1_paragraph.content
    assert section_1_paragraph.page_or_anchor == "p.1"
    assert section_1_paragraph.chapter == "10"

    section_3_paragraph = next(c for c in paragraphs if c.section == "10.16.3")
    assert section_3_paragraph.content == _PAGE2_PARAGRAPH
    assert section_3_paragraph.page_or_anchor == "p.2"

    tables = by_kind["table"]
    assert len(tables) == 1
    table_chunk = tables[0]
    assert table_chunk.section == "10.16.2.2"
    assert table_chunk.page_or_anchor == "p.1"
    for row in _TABLE_ROWS:
        assert " | ".join(row) in table_chunk.content


def test_chunk_pdf_chunk_ids_are_unique(synthetic_pdf):
    chunks = _chunk_pdf(synthetic_pdf)
    assert len(chunks) == len({c.chunk_id for c in chunks})


def test_verify_source_hash_rejects_tampered_content(synthetic_pdf):
    with pytest.raises(PdfIngestionError, match="content_sha256 mismatch"):
        verify_source_hash(synthetic_pdf, "0" * 64)


def test_chunk_pdf_fails_closed_on_wrong_expected_hash(synthetic_pdf):
    with pytest.raises(PdfIngestionError, match="content_sha256 mismatch"):
        _chunk_pdf(synthetic_pdf, expected_sha256="0" * 64)


def test_chunk_pdf_rejects_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.pdf"
    with pytest.raises(PdfIngestionError, match="does not exist"):
        chunk_pdf(
            missing,
            source_id="usb32_synth",
            document="USB 3.2 Specification",
            revision="Rev 1.1",
            authority_level="authoritative",
            expected_sha256="0" * 64,
        )


def test_search_chunks_matches_content_case_insensitively(synthetic_pdf):
    chunks = _chunk_pdf(synthetic_pdf)
    hits = search_chunks(chunks, "port_power")
    assert hits
    assert all("port_power" in c.content.lower() for c in hits)
    assert search_chunks(chunks, "nonexistent phrase xyz") == []


def _corpus_lock(source_locator: str, expected_sha256: str) -> dict:
    return {
        "layers": {
            "official_raw": {"allowed_as_answer_evidence": True},
            "draft_only": {"allowed_as_answer_evidence": False},
        },
        "sources": {
            "usb32_synth": {
                "document": "USB 3.2 Specification",
                "revision": "Rev 1.1",
                "role": "normative_official",
                "layer": "official_raw",
                "phase": "phase_1",
                "included": True,
                "source_locator": source_locator,
                "content_sha256": expected_sha256,
            },
            "usb32_draft_excluded": {
                "document": "USB 3.2 Specification",
                "revision": "Rev 1.1",
                "role": "normative_official",
                "layer": "draft_only",
                "phase": "phase_1",
                "included": True,
                "source_locator": source_locator,
                # Deliberately wrong -- this source must never be hashed or
                # ingested at all, since its layer disallows answer evidence.
                "content_sha256": "0" * 64,
            },
        },
    }


def test_resolve_source_locator_with_raw_root_override(tmp_path):
    resolved = resolve_source_locator(
        "env://USB_SPEC_QA_RAW_ROOT/subdir/usb32.pdf", raw_root=tmp_path
    )
    assert resolved == tmp_path / "subdir" / "usb32.pdf"


def test_resolve_source_locator_requires_env_var_when_no_override(monkeypatch):
    monkeypatch.delenv("USB_SPEC_QA_RAW_ROOT", raising=False)
    with pytest.raises(PdfIngestionError, match="not set"):
        resolve_source_locator("env://USB_SPEC_QA_RAW_ROOT/usb32.pdf")


def test_resolve_source_locator_rejects_unsupported_format():
    with pytest.raises(PdfIngestionError, match="unsupported source_locator"):
        resolve_source_locator("https://example.com/usb32.pdf")


def test_is_source_eligible_as_answer_evidence_respects_layer_and_phase():
    lock = _corpus_lock("env://USB_SPEC_QA_RAW_ROOT/usb32.pdf", "0" * 64)
    assert is_source_eligible_as_answer_evidence("usb32_synth", lock) is True
    assert is_source_eligible_as_answer_evidence("usb32_draft_excluded", lock) is False
    assert is_source_eligible_as_answer_evidence("unknown_source", lock) is False


def test_ingest_source_from_corpus_lock_uses_raw_root_and_locked_hash(synthetic_pdf, tmp_path):
    lock = _corpus_lock("env://USB_SPEC_QA_RAW_ROOT/usb32_synthetic.pdf", _sha256_of(synthetic_pdf))
    chunks = ingest_source_from_corpus_lock("usb32_synth", lock, raw_root=tmp_path)
    assert chunks
    assert all(c.source_id == "usb32_synth" for c in chunks)


def test_load_accepted_chunks_skips_ineligible_sources_without_ingesting_them(
    synthetic_pdf, tmp_path
):
    lock = _corpus_lock("env://USB_SPEC_QA_RAW_ROOT/usb32_synthetic.pdf", _sha256_of(synthetic_pdf))
    chunks = load_accepted_chunks(["usb32_synth", "usb32_draft_excluded"], lock, raw_root=tmp_path)
    # usb32_draft_excluded has a deliberately wrong locked hash -- if it were
    # ever ingested, this would raise PdfIngestionError instead of just
    # being filtered out.
    assert chunks
    assert all(c.source_id == "usb32_synth" for c in chunks)
