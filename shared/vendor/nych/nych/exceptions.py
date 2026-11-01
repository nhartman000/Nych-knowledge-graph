"""
NYCH Custom Exceptions
======================
Domain-specific exceptions for the NYCH pipeline.
"""

from __future__ import annotations


class NYCHException(Exception):
    """Base exception for all NYCH errors."""
    pass


class IngestionError(NYCHException):
    """Raised when input cannot be ingested or normalized."""
    pass


class SymbolizationError(NYCHException):
    """Raised when symbolization fails or produces invalid output."""
    pass


class DomainExpansionError(NYCHException):
    """Raised when domain expansion cannot produce admissible candidates."""
    pass


class ConstraintViolationError(NYCHException):
    """Raised when a candidate violates constraints."""
    pass


class TOTEError(NYCHException):
    """Raised when TOTE execution fails or exceeds bounds."""
    pass


class ValidationError(NYCHException):
    """Raised when validation fails."""
    pass


class SchemaValidationError(NYCHException):
    """Raised when emitted artifact fails schema validation."""
    pass


class StateChronologyError(NYCHException):
    """Raised when state chronology is violated."""
    pass


class AnomalyDetectedError(NYCHException):
    """Raised when an anomaly triggers the slow path."""
    pass
