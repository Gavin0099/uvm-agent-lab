import json
import hashlib
from typing import Dict, Any, List, Optional
from retrieval.canonical.retriever import CanonicalSpecRetriever


class SpecReferenceKitMCPServer:
    """
    Model Context Protocol (MCP) Server for the 'spec-reference-kit' Governed Knowledge Layer.
    Implements standard JSON-RPC 2.0 protocol interface for tool discovery and invocation.
    """

    def __init__(self, spec_dir: str = "fixtures/synthetic-spec"):
        self.retriever = CanonicalSpecRetriever(spec_dir=spec_dir)

    def get_manifest(self) -> Dict[str, Any]:
        """
        MCP Tool Manifest listing available capabilities and parameter schemas.
        """
        return {
            "name": "spec-reference-kit",
            "version": "1.0.0",
            "tools": [
                {
                    "name": "get_authoritative_spec",
                    "description": "Retrieve certified, version-pinned specification clauses with provenance hash.",
                    "parameters": {
                        "type": "object",
                        "required": ["requirement_id"],
                        "properties": {
                            "requirement_id": {"type": "string", "description": "Unique Requirement ID (e.g. USB3-WR-001)"},
                            "target_version": {"type": "string", "description": "Target protocol version (e.g. '1.0', '2.1')"},
                            "customer_tier": {"type": "string", "description": "Caller customer authorization tier"}
                        }
                    }
                },
                {
                    "name": "list_valid_specs",
                    "description": "List all authoritative specifications available in the knowledge repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_tier": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "verify_clause_hash",
                    "description": "Verify cryptographic authenticity of a spec snippet against canonical hash.",
                    "parameters": {
                        "type": "object",
                        "required": ["requirement_id", "canonical_hash"],
                        "properties": {
                            "requirement_id": {"type": "string"},
                            "canonical_hash": {"type": "string"}
                        }
                    }
                }
            ]
        }

    def handle_request(self, json_rpc_req: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes standard JSON-RPC 2.0 requests.
        """
        req_id = json_rpc_req.get("id", 1)
        method = json_rpc_req.get("method")
        params = json_rpc_req.get("params", {})

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": self.get_manifest()
            }

        if method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})

            if tool_name == "get_authoritative_spec":
                req_clause_id = args.get("requirement_id")
                ver = args.get("target_version")
                tier = args.get("customer_tier", "internal_engineering")

                hits = self.retriever.query(
                    query_str=req_clause_id,
                    top_k=1,
                    target_version=ver,
                    caller_customer_tier=tier
                )

                if hits:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "status": "success",
                            "clause": hits[0]
                        }
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "status": "not_found",
                            "message": f"Requirement '{req_clause_id}' not found or access unauthorized for tier '{tier}'."
                        }
                    }

            elif tool_name == "list_valid_specs":
                tier = args.get("customer_tier", "internal_engineering")
                valid_docs = [
                    {"file": d["file"], "title": d["title"], "version": d["version"], "doc_id": d["doc_id"]}
                    for d in self.retriever._index
                    if d["authority"] == "authoritative" and (d["customer_tier"] != "tier_a_partner_restricted" or tier == "tier_a_partner_restricted")
                ]
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"specs": valid_docs}
                }

            elif tool_name == "verify_clause_hash":
                req_clause_id = args.get("requirement_id")
                target_hash = args.get("canonical_hash")
                hits = self.retriever.query(query_str=req_clause_id, top_k=1)
                if hits and hits[0]["canonical_hash"] == target_hash:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"status": "verified", "authentic": True}
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"status": "hash_mismatch", "authentic": False}
                    }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found."}
        }
