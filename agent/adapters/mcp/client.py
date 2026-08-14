from typing import Dict, Any, Optional
from agent.adapters.mcp.server import SpecReferenceKitMCPServer


class SpecReferenceKitMCPClient:
    """
    Client for interacting with the SpecReferenceKitMCPServer via Model Context Protocol.
    """

    def __init__(self, server: Optional[SpecReferenceKitMCPServer] = None):
        self.server = server or SpecReferenceKitMCPServer()

    def list_tools(self) -> Dict[str, Any]:
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        return self.server.handle_request(req).get("result", {})

    def get_authoritative_spec(self, requirement_id: str, target_version: Optional[str] = None, customer_tier: Optional[str] = None) -> Dict[str, Any]:
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_authoritative_spec",
                "arguments": {
                    "requirement_id": requirement_id,
                    "target_version": target_version,
                    "customer_tier": customer_tier
                }
            }
        }
        return self.server.handle_request(req).get("result", {})

    def verify_hash(self, requirement_id: str, canonical_hash: str) -> bool:
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "verify_clause_hash",
                "arguments": {
                    "requirement_id": requirement_id,
                    "canonical_hash": canonical_hash
                }
            }
        }
        res = self.server.handle_request(req).get("result", {})
        return res.get("authentic", False)
