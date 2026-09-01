import hashlib
import sys
from types import SimpleNamespace
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
    is_official_raw_pdf_source,
    is_source_eligible_as_answer_evidence,
    load_accepted_chunks,
    parse_included_chapters,
    resolve_source_locator,
    search_chunks,
    verify_source_hash,
)
import gv100h.spec_qa.ingestion.pdf_ingestion as pdf_ingestion

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


# A second synthetic PDF spanning two chapters (6 and 8), standing in for the
# real corpus.lock.yaml situation where usb20_fw/usb20_se both point at the
# SAME usb_20.pdf file but declare different `included_chapters` -- proves
# Phase-1 chapter scoping is enforced per-source, not just per-PDF-file.
_CHAPTER6_MARKER = "CHAPTER SIX HUB REPEATER CONTENT"
_CHAPTER8_MARKER = "CHAPTER EIGHT PROTOCOL LAYER CONTENT"


def _build_multi_chapter_pdf(path: Path) -> None:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=11)
    pdf.add_page()
    pdf.multi_cell(0, 6, "6.1 Hub Repeater")
    pdf.ln(4)
    pdf.multi_cell(0, 6, _CHAPTER6_MARKER)
    pdf.ln(4)
    pdf.multi_cell(0, 6, "8.1 Protocol Layer")
    pdf.ln(4)
    pdf.multi_cell(0, 6, _CHAPTER8_MARKER)
    pdf.output(str(path))


@pytest.fixture()
def multi_chapter_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "multi_chapter.pdf"
    _build_multi_chapter_pdf(pdf_path)
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


def test_chunk_pdf_skips_blank_table_detections(synthetic_pdf, monkeypatch):
    monkeypatch.setattr(
        pdf_ingestion,
        "_page_events",
        lambda page: [
            (0.0, "line", "10.1 Nonempty Section"),
            (1.0, "table", [[""], ["  "]]),
        ],
    )
    chunks = _chunk_pdf(synthetic_pdf)
    assert chunks
    assert all(chunk.chunk_kind == "heading_only" for chunk in chunks)


def test_page_events_drops_usb_page_furniture_and_toc_entries():
    page = SimpleNamespace(
        height=792.0,
        find_tables=lambda: [],
        extract_text_lines=lambda layout=False: [
            {"text": "Revision 1.1 - 104 - Universal Serial Bus 3.2", "top": 37.0, "bottom": 47.0},
            {"text": "June 2022 Specification", "top": 49.0, "bottom": 59.0},
            {"text": "6.9.3 Warm Reset ................................................................................. 104", "top": 74.0, "bottom": 84.0},
            {"text": "6.9.3 Warm Reset", "top": 90.0, "bottom": 100.0},
            {"text": "Copyright © 2022 USB 3.0 Promoter Group. All rights reserved.", "top": 746.0, "bottom": 756.0},
        ],
    )
    events = pdf_ingestion._page_events(page)
    assert [(kind, payload) for _, kind, payload in events] == [
        ("line", "6.9.3 Warm Reset"),
    ]


def test_chunk_pdf_chunk_ids_are_unique(synthetic_pdf):
    chunks = _chunk_pdf(synthetic_pdf)
    assert len(chunks) == len({c.chunk_id for c in chunks})


def test_parse_included_chapters_expands_ranges_and_bare_entries():
    assert parse_included_chapters(["5", "8-11"]) == frozenset({"5", "8", "9", "10", "11"})


def test_parse_included_chapters_rejects_unrecognized_entry():
    with pytest.raises(PdfIngestionError, match="unrecognized included_chapters"):
        parse_included_chapters(["not-a-chapter"])


def test_chunk_pdf_included_chapters_excludes_disallowed_chapter(multi_chapter_pdf):
    # P1 regression: being a locked/hash-verified source is NOT itself
    # authorization to cite every chapter in that PDF -- corpus.lock.yaml's
    # per-source included_chapters allowlist must be enforced at chunk
    # creation time, not left to whatever headings happen to be in the PDF.
    chunks = _chunk_pdf(multi_chapter_pdf, included_chapters=["6"])
    assert chunks
    assert {c.chapter for c in chunks} == {"6"}
    assert all(_CHAPTER8_MARKER not in c.content for c in chunks)
    assert any(_CHAPTER6_MARKER in c.content for c in chunks)


def test_chunk_pdf_included_chapters_supports_inclusive_ranges(multi_chapter_pdf):
    chunks = _chunk_pdf(multi_chapter_pdf, included_chapters=["8-11"])
    assert chunks
    assert {c.chapter for c in chunks} == {"8"}
    assert all(_CHAPTER6_MARKER not in c.content for c in chunks)


def test_chunk_pdf_without_included_chapters_keeps_every_chapter(multi_chapter_pdf):
    # None means "no chapter restriction declared for this source", the
    # backward-compatible default for direct chunk_pdf() callers -- not
    # "all chapters pre-approved" as a corpus.lock.yaml policy statement.
    chunks = _chunk_pdf(multi_chapter_pdf)
    assert {c.chapter for c in chunks} == {"6", "8"}


def test_chunk_pdf_fails_closed_when_included_chapters_matches_nothing(multi_chapter_pdf):
    with pytest.raises(PdfIngestionError, match="included_chapters"):
        _chunk_pdf(multi_chapter_pdf, included_chapters=["99"])


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


def test_resolve_source_locator_rejects_dotdot_traversal_escape(tmp_path):
    root_dir = tmp_path / "raw_root"
    root_dir.mkdir()
    with pytest.raises(PdfIngestionError, match="escapes its source root"):
        resolve_source_locator(
            "env://USB_SPEC_QA_RAW_ROOT/../outside.pdf", raw_root=root_dir
        )


def test_resolve_source_locator_rejects_absolute_relative_path_escape(tmp_path):
    root_dir = tmp_path / "raw_root"
    root_dir.mkdir()
    outside_file = tmp_path / "outside.pdf"
    # The locator format is "env://<VAR>/<relative_path>": the parser splits
    # off <VAR> at the *first* "/" it sees, so that one "/" is a deliberate
    # separator, not part of <relative_path> itself. To make <relative_path>
    # equal to the host OS's own native absolute-path spelling of
    # outside_file (e.g. "/tmp/x/outside.pdf" on POSIX, or
    # "C:/Users/x/outside.pdf" on Windows), it must be placed *after* that
    # one separator verbatim -- not have its own leading "/" folded into the
    # single separator, which would silently turn it into an in-bounds
    # relative path on POSIX (Path("/tmp/x").is_absolute() is True, but
    # Path("tmp/x").is_absolute() is False) while still working "by
    # accident" on Windows (a drive letter is absolute with or without a
    # leading "/").
    native_absolute_path = str(outside_file).replace("\\", "/")
    with pytest.raises(PdfIngestionError, match="absolute|escapes its source root"):
        resolve_source_locator(
            f"env://USB_SPEC_QA_RAW_ROOT/{native_absolute_path}", raw_root=root_dir
        )


def test_resolve_source_locator_accepts_normal_file_within_root(tmp_path):
    root_dir = tmp_path / "raw_root"
    (root_dir / "subdir").mkdir(parents=True)
    resolved = resolve_source_locator(
        "env://USB_SPEC_QA_RAW_ROOT/subdir/usb32.pdf", raw_root=root_dir
    )
    assert resolved == (root_dir / "subdir" / "usb32.pdf").resolve()


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


@pytest.mark.parametrize(
    "source_overrides",
    [
        {"phase": "phase_2"},
        {"included": False},
        {"layer": "evaluation_only"},
    ],
)
def test_ingest_source_from_corpus_lock_rejects_ineligible_sources(
    synthetic_pdf, tmp_path, source_overrides
):
    """The direct ingestion entry point must enforce the same corpus
    eligibility boundary as load_accepted_chunks: evaluation-only, Phase-2,
    and explicitly excluded sources must never become GovernedChunks merely
    because a caller invokes this lower-level function directly."""
    lock = _corpus_lock("env://USB_SPEC_QA_RAW_ROOT/usb32_synthetic.pdf", _sha256_of(synthetic_pdf))
    if source_overrides.get("layer") == "evaluation_only":
        lock["layers"]["evaluation_only"] = {"allowed_as_answer_evidence": False}
    lock["sources"]["usb32_synth"].update(source_overrides)
    with pytest.raises(PdfIngestionError, match="not eligible"):
        ingest_source_from_corpus_lock("usb32_synth", lock, raw_root=tmp_path)


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


def test_ingest_source_from_corpus_lock_enforces_included_chapters(multi_chapter_pdf, tmp_path):
    lock = _corpus_lock(
        "env://USB_SPEC_QA_RAW_ROOT/multi_chapter.pdf", _sha256_of(multi_chapter_pdf)
    )
    lock["sources"]["usb32_synth"]["included_chapters"] = ["6"]
    chunks = ingest_source_from_corpus_lock("usb32_synth", lock, raw_root=tmp_path)
    assert chunks
    assert {c.chapter for c in chunks} == {"6"}
    assert all(_CHAPTER8_MARKER not in c.content for c in chunks)


def test_same_pdf_different_corpus_sources_yield_different_chunk_scopes(
    multi_chapter_pdf, tmp_path
):
    """
    Mirrors the real corpus.lock.yaml situation: usb20_fw and usb20_se both
    point at the SAME usb_20.pdf file but declare different
    included_chapters. Ingesting the identical PDF bytes through two
    different corpus.lock.yaml source entries must yield two DIFFERENT
    GovernedChunk sets -- proving chapter governance is scoped per source
    declaration, not just per physical PDF file.
    """
    sha = _sha256_of(multi_chapter_pdf)
    lock = {
        "layers": {"official_raw": {"allowed_as_answer_evidence": True}},
        "sources": {
            "usb20_fw_like": {
                "document": "USB 2.0 Specification",
                "revision": "2.0",
                "role": "normative_official",
                "layer": "official_raw",
                "phase": "phase_1",
                "included": True,
                "included_chapters": ["6"],
                "source_locator": "env://USB_SPEC_QA_RAW_ROOT/multi_chapter.pdf",
                "content_sha256": sha,
            },
            "usb20_se_like": {
                "document": "USB 2.0 Specification",
                "revision": "2.0",
                "role": "normative_official",
                "layer": "official_raw",
                "phase": "phase_1",
                "included": True,
                "included_chapters": ["8-11"],
                "source_locator": "env://USB_SPEC_QA_RAW_ROOT/multi_chapter.pdf",
                "content_sha256": sha,
            },
        },
    }
    fw_chunks = ingest_source_from_corpus_lock("usb20_fw_like", lock, raw_root=tmp_path)
    se_chunks = ingest_source_from_corpus_lock("usb20_se_like", lock, raw_root=tmp_path)
    assert {c.chapter for c in fw_chunks} == {"6"}
    assert {c.chapter for c in se_chunks} == {"8"}
    assert {c.chunk_id for c in fw_chunks}.isdisjoint({c.chunk_id for c in se_chunks})


def _lock_with_governed_reference_source(source_locator: str, expected_sha256: str) -> dict:
    lock = _corpus_lock(source_locator, expected_sha256)
    lock["layers"]["governed_reference"] = {"allowed_as_answer_evidence": True}
    lock["sources"]["hub_reference_like"] = {
        "document": "USB-IF Hub Class Governed Reference",
        "revision": "N/A",
        "role": "canonical_structured_reference",
        "layer": "governed_reference",
        "phase": "phase_1",
        "included": True,
        # A legitimate answer-evidence source that is NOT a PDF this
        # pipeline understands -- mirrors the real hub_reference entry's
        # repo:// locator in corpus.lock.yaml.
        "source_locator": "repo://Gavin0099/usb-if-hub-spec-reference@deadbeef",
        "content_sha256": "0" * 64,
    }
    return lock


def test_is_official_raw_pdf_source_distinguishes_pdf_from_non_pdf_evidence(synthetic_pdf):
    lock = _lock_with_governed_reference_source(
        "env://USB_SPEC_QA_RAW_ROOT/usb32_synthetic.pdf", _sha256_of(synthetic_pdf)
    )
    assert is_official_raw_pdf_source("usb32_synth", lock) is True
    assert is_official_raw_pdf_source("hub_reference_like", lock) is False


def test_load_accepted_chunks_skips_eligible_non_pdf_locator_sources(synthetic_pdf, tmp_path):
    lock = _lock_with_governed_reference_source(
        "env://USB_SPEC_QA_RAW_ROOT/usb32_synthetic.pdf", _sha256_of(synthetic_pdf)
    )
    # hub_reference_like IS eligible as answer evidence (layer allows it,
    # phase_1, included) but must be skipped here rather than attempted --
    # attempting it would misuse its repo:// locator as if it were a PDF
    # env:// path.
    chunks = load_accepted_chunks(["usb32_synth", "hub_reference_like"], lock, raw_root=tmp_path)
    assert chunks
    assert all(c.source_id == "usb32_synth" for c in chunks)

