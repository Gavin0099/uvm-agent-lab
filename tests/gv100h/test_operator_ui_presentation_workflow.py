"""Operator UI presentation *workflow contract* lock.

These tests prove routing + proposal files still exist.
They do NOT prove UX quality, visual hierarchy, or that a redesign
was implemented.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FRONTEND_SKILL = REPO / ".agents/skills/frontend-design/SKILL.md"
UX_SKILL = REPO / ".agents/skills/ui-ux-review/SKILL.md"
PROPOSAL = REPO / "docs/operator-ui-ia-ux-redesign.md"
AGENTS = REPO / "AGENTS.md"
STATIC = REPO / "gv100h/spec_qa/operator_ui/static"


def test_operator_ui_skills_are_present_and_stack_locked():
    frontend = FRONTEND_SKILL.read_text(encoding="utf-8")
    ux = UX_SKILL.read_text(encoding="utf-8")
    assert frontend.startswith("---")
    assert "name: frontend-design" in frontend
    assert "AGENTS.md" in frontend
    assert "before" in frontend
    assert "React" in frontend and "Tailwind" in frontend
    assert "QAResponse" in frontend
    assert ux.startswith("---")
    assert "name: ui-ux-review" in ux
    assert "let this skill drive the first design" in ux
    assert "rendered-UI review" in ux or "rendered UI" in ux
    assert "Do not approve from HTML/CSS/JS reading alone" in ux
    assert "React" in ux and "Tailwind" in ux


def test_ia_ux_proposal_is_frozen_not_implemented():
    text = PROPOSAL.read_text(encoding="utf-8")
    assert "frozen IA/UX proposal" in text
    assert "does not change" in text
    assert "Ask → Answer → Source" in text or "what was asked" in text
    assert "50/50" in text
    assert "Advanced" in text
    assert "feat/spec-qa-operator-ui-redesign" in text
    assert "prove UX quality" in text
    assert "POC-1" in text
    assert "QAResponse" in text
    assert "React" in text
    assert "1440" in text and "390" in text


def test_agents_md_requires_read_skills_and_rendered_review():
    text = AGENTS.read_text(encoding="utf-8")
    assert "governance:key=operator_ui_presentation" in text
    assert "When modifying `gv100h/spec_qa/operator_ui/static/**`:" in text
    assert "Read `.agents/skills/frontend-design/SKILL.md`" in text
    assert "Produce or update the IA/UX proposal" in text
    assert "Do not modify `QAResponse`" in text
    assert "After implementation, read `.agents/skills/ui-ux-review/SKILL.md`" in text
    assert "Review screenshot or rendered UI, not source code only" in text
    assert "1440" in text and "390" in text
    assert "does **not** prove UX quality" in text
    frontend_at = text.index("Read `.agents/skills/frontend-design/SKILL.md`")
    proposal_at = text.index("Produce or update the IA/UX proposal")
    impl_marker = text.index("After implementation, read `.agents/skills/ui-ux-review/SKILL.md`")
    screenshot_at = text.index("Review screenshot or rendered UI, not source code only")
    assert frontend_at < proposal_at < impl_marker < screenshot_at


def test_this_slice_does_not_rewrite_static_shell():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "answer_scope" in html
    assert "retrieval_mode" in html
    assert "allowed_evidence_scopes" in html
    assert "DATA SOURCE" in html
    assert "grid-template-columns: 1fr 1fr" in css
    assert "innerHTML" not in js
