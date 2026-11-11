"""Opt-in evidence-only search; existing production/LLM entry is untouched."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gv100h.spec_qa.evidence_first.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
