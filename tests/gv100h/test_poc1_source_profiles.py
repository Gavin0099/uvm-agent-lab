"""Profile identity tests, with no admission/evaluator or PDF execution."""
import pytest

from gv100h.spec_qa.contracts.poc1_source_profiles import (
    POC1SourceProfileError, POC1_V1_SOURCE_PROFILE_ID, POC1_V2_PDF_SOURCE_PROFILE_ID,
    resolve_poc1_source_profile,
)


@pytest.mark.parametrize("name", [None, POC1_V1_SOURCE_PROFILE_ID])
def test_v1_default_remains_the_original_five_source_contract(name):
    result = resolve_poc1_source_profile(schema_version="1.1", source_profile_id=name)
    assert result.required_source_ids == ("hub_reference", "usb20_fw", "usb20_se", "usb32", "superspeed_hub_lvs")
    assert result.binding_mode == "whole_phase1_corpus"


def test_v2_is_explicit_pdf_only_and_does_not_replace_v1_default():
    result = resolve_poc1_source_profile(schema_version="1.2", source_profile_id=POC1_V2_PDF_SOURCE_PROFILE_ID)
    assert result.required_source_ids == ("usb20_fw", "usb20_se", "usb32", "superspeed_hub_lvs")
    assert result.binding_mode == "receipt_bound_official_pdf_corpus"
    assert "hub_reference" in resolve_poc1_source_profile(schema_version="1.1", source_profile_id=None).required_source_ids


@pytest.mark.parametrize("version,name", [("1.1", POC1_V2_PDF_SOURCE_PROFILE_ID), ("1.2", None), ("1.2", POC1_V1_SOURCE_PROFILE_ID), ("1.2", "unknown"), ("2.0", None)])
def test_unknown_or_cross_version_profile_is_rejected(version, name):
    with pytest.raises(POC1SourceProfileError):
        resolve_poc1_source_profile(schema_version=version, source_profile_id=name)
