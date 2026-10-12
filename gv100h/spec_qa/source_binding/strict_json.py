"""Strict JSON-object decoding, independent of runtime or benchmark adapters."""
import json

def strict_object(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def bad_constant(_):
        raise ValueError("nonstandard JSON number")
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=bad_constant)
    if not isinstance(value, dict):
        raise ValueError("one JSON object required")
    # A syntactically legal exponent can overflow Python's JSON float parser.
    # Reject it recursively before exposing a payload that cannot be JSON again.
    json.dumps(value, allow_nan=False)
    return value
