"""
Legacy NYCH state profile, not the dedicated canonical GST format.
Historical to_canonical names normalize prior/current and internal/external
state records only; they do not establish external format conformance.
"""

from __future__ import annotations

from typing import Any

from nych.exceptions import SchemaValidationError
from nych.schemas import SchemaValidator


PROFILE_ID = "nych.legacy.gst-state.v1"

# Legacy NYCH profile definition
_GST_SCHEMA = {
    "type": "object",
    "required": ["state"],
    "properties": {
        "state": {
            "type": "object",
            "required": ["prior", "current"],
            "properties": {
                "prior": {"type": ["object", "null"]},
                "current": {"type": ["object", "null"]},
                "internal_prior": {"type": ["object", "null"]},
                "internal_current": {"type": ["object", "null"]},
                "external_prior": {"type": ["object", "null"]},
                "external_current": {"type": ["object", "null"]},
                "continuity_reference": {"type": ["string", "null"]},
            },
        },
    },
}


class GSTValidator(SchemaValidator):
    """Validator for the legacy NYCH state profile only."""
    
    def validate(self, data: dict[str, Any]) -> bool:
        """Validate the legacy NYCH GST profile only."""
        if not isinstance(data, dict):
            raise SchemaValidationError("GST data must be a dictionary")
        
        if "state" not in data:
            raise SchemaValidationError("GST data missing required 'state' field")
        
        state = data["state"]
        if not isinstance(state, dict):
            raise SchemaValidationError("GST 'state' must be a dictionary")
        
        if "prior" not in state and "current" not in state:
            raise SchemaValidationError("GST state must have at least 'prior' or 'current'")
        
        return True
    
    def to_canonical(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize the legacy NYCH profile in place; historical API name."""
        if "state" not in data:
            data["state"] = {}
        
        state = data["state"]
        state.setdefault("prior", None)
        state.setdefault("current", None)
        state.setdefault("internal_prior", None)
        state.setdefault("internal_current", None)
        state.setdefault("external_prior", None)
        state.setdefault("external_current", None)
        state.setdefault("continuity_reference", None)
        
        return data


def validate_gst(data: dict[str, Any]) -> bool:
    """Validate legacy NYCH GST data. Returns True if valid."""
    validator = GSTValidator()
    return validator.validate(data)


def to_canonical_gst(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize the legacy NYCH profile in place; not a format migration."""
    validator = GSTValidator()
    return validator.to_canonical(data)
