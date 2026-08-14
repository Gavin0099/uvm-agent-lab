import pytest
from agent.adapters.mcp.client import SpecReferenceKitMCPClient


def test_mcp_manifest_discovery():
    client = SpecReferenceKitMCPClient()
    manifest = client.list_tools()
    
    assert manifest["name"] == "spec-reference-kit"
    tool_names = [t["name"] for t in manifest["tools"]]
    assert "get_authoritative_spec" in tool_names
    assert "list_valid_specs" in tool_names
    assert "verify_clause_hash" in tool_names


def test_mcp_tool_invocation_and_provenance():
    client = SpecReferenceKitMCPClient()
    res = client.get_authoritative_spec(requirement_id="USB3-WR-001")
    
    assert res["status"] == "success"
    clause = res["clause"]
    assert "USB3-WR-001" in clause["snippet"]
    assert clause["canonical_hash"].startswith("sha256:")

    # Verify cryptographic hash check
    is_authentic = client.verify_hash(requirement_id="USB3-WR-001", canonical_hash=clause["canonical_hash"])
    assert is_authentic is True

    # Negative test on tampered hash
    is_tampered_authentic = client.verify_hash(requirement_id="USB3-WR-001", canonical_hash="sha256:fakehash12345")
    assert is_tampered_authentic is False
