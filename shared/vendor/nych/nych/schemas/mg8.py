"""
Legacy NYCH MG8 container profile, not the dedicated canonical MG8 format.
Historical to_canonical names normalize this local orchestration/state/gates/
evidence shape only; they do not migrate to the resource-manifest format.
"""

from __future__ import annotations

from typing import Any

from nych.exceptions import SchemaValidationError
from nych.schemas import SchemaValidator


PROFILE_ID = "nych.legacy.mg8-container.v1"

# Legacy NYCH profile definition
_MG8_SCHEMA = {
    "type": "object",
    "required": ["orchestration", "state", "gates", "evidence"],
    "properties": {
        "orchestration": {
            "type": "object",
            "properties": {
                "pipeline_id": {"type": "string"},
                "run_id": {"type": "string"},
                "timestamp": {"type": "string"},
                "config": {"type": "object"},
            },
        },
        "state": {
            "type": "object",
            "properties": {
                "gst_ref": {"type": "string"},
                "nych_ref": {"type": "string"},
            },
        },
        "gates": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["g8son_ref"],
                "properties": {
                    "g8son_ref": {"type": "string"},
                    "result": {"type": "boolean"},
                },
            },
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["qson_ref"],
                "properties": {
                    "qson_ref": {"type": "string"},
                    "event_type": {"type": "string"},
                },
            },
        },
    },
}


class MG8Validator(SchemaValidator):
    """Validator for the legacy NYCH MG8 container profile only."""
    
    def validate(self, data: dict[str, Any]) -> bool:
        """Validate the legacy NYCH MG8 profile only."""
        if not isinstance(data, dict):
            raise SchemaValidationError("MG8 data must be a dictionary")
        
        required_sections = ["orchestration", "state", "gates", "evidence"]
        for section in required_sections:
            if section not in data:
                raise SchemaValidationError(f"MG8 data missing required section: {section}")
        
        # Validate orchestration
        orchestration = data["orchestration"]
        if not isinstance(orchestration, dict):
            raise SchemaValidationError("MG8 'orchestration' must be a dictionary")
        
        # Validate state
        state = data["state"]
        if not isinstance(state, dict):
            raise SchemaValidationError("MG8 'state' must be a dictionary")
        
        # Validate gates
        gates = data["gates"]
        if not isinstance(gates, list):
            raise SchemaValidationError("MG8 'gates' must be a list")
        
        for i, gate in enumerate(gates):
            if not isinstance(gate, dict):
                raise SchemaValidationError(f"Gate {i} must be a dictionary")
            if "g8son_ref" not in gate:
                raise SchemaValidationError(f"Gate {i} missing 'g8son_ref'")
        
        # Validate evidence
        evidence = data["evidence"]
        if not isinstance(evidence, list):
            raise SchemaValidationError("MG8 'evidence' must be a list")
        
        for i, ev in enumerate(evidence):
            if not isinstance(ev, dict):
                raise SchemaValidationError(f"Evidence {i} must be a dictionary")
            if "qson_ref" not in ev:
                raise SchemaValidationError(f"Evidence {i} missing 'qson_ref'")
        
        return True
    
    def to_canonical(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize the legacy NYCH profile in place; historical API name."""
        required_sections = ["orchestration", "state", "gates", "evidence"]
        for section in required_sections:
            if section not in data:
                if section == "gates":
                    data[section] = []
                elif section == "evidence":
                    data[section] = []
                else:
                    data[section] = {}
        
        return data


def validate_mg8(data: dict[str, Any]) -> bool:
    """Validate legacy NYCH MG8 data. Returns True if valid."""
    validator = MG8Validator()
    return validator.validate(data)


def to_canonical_mg8(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize the legacy NYCH profile in place; not a format migration."""
    validator = MG8Validator()
    return validator.to_canonical(data)
