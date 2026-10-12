"""Public table identity only; no question answer schema or Gold values."""

IDENTITY_SCHEMA = "spec_qa_table_identity.candidate.v0.2"

def table_identity_schema():
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": IDENTITY_SCHEMA,
        "type": "object", "additionalProperties": False,
        "required": ["source_id", "revision", "number"], "properties": {
            "source_id": {"type": "string", "minLength": 1, "pattern": r"^\S+$",
                "description": "Copy the source_id of the cited evidence exactly."},
            "revision": {"type": "string", "minLength": 1, "pattern": r"\S",
                "description": "Copy the cited document revision exactly, not the execution contract version."},
            "number": {"type": "string", "pattern": r"^[0-9]+(?:-[0-9]+)?$",
                "description": "Copy the genuine cited caption's table number, omitting Table and its terminating period."}}}
