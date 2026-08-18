import pytest
import tempfile
from pathlib import Path
from validators.verification_scope_validator import validate_scope
from validators.zero_trust_evidence_validator import validate_evidence


def test_verification_scope_validator_execution():
    assert validate_scope() is True


def test_zero_trust_evidence_validator_execution():
    assert validate_evidence() is True
