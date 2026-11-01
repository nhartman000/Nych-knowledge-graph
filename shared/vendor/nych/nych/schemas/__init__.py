"""
NYCH Schema Adapters/Validators
================================
Legacy NYCH profile validators, not the dedicated canonical formats.
Historical to_canonical method names normalize local records only.
"""

from __future__ import annotations

from typing import Any

from nych.exceptions import SchemaValidationError


class SchemaValidator:
    """Base class for schema validators."""
    
    def validate(self, data: dict[str, Any]) -> bool:
        """Validate data against schema. Returns True if valid."""
        raise NotImplementedError
    
    def to_canonical(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize a legacy NYCH profile; historical method name."""
        raise NotImplementedError
