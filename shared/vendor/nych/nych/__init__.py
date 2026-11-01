"""
NYCH Symbolic Pipeline
=====================
A cohesive NYCH pipeline with explicit typed boundaries.

This package implements the NYCH symbolic-control architecture:
- Accepts natural language or sensor input
- Normalizes both into a shared NYCH packet/state model
- Constrains the action/state space
- Runs admissible reasoning/execution
- Validates the result
- Emits canonical evidence

Architecture layers (per canonical rule set):
1. INGEST: accept NaturalLanguageInput | SensorInput | ExistingSymbolicPacket
2. IDENTITY / VERNACULAR: determine speaker/narrative perspective, competency
3. FEATURE NORMALIZATION: preserve numbers; convert sensor patterns
4. INVARIANT EXTRACTION: modality, person, tense, operators, domain markers
5. SYMBOLIZATION: select semantic anchor; produce consonant skeleton
6. CONTEXT BUILD: Domain + Subject + Intent + Competency + tools + state
7. DOMAIN EXPANSION: Domain -> Discipline -> Function -> Technique -> TOTE
8. INVERSE TRANSFORM / CONSTRAINT MASK: reject inadmissible candidates
9. CANDIDATE SELECTION: deterministic or probabilistic within boundary
10. TOTE EXECUTION: Test -> Operate -> Test -> Exit
11. CONTINUITY VALIDATION: prior/current, internal/external, operators
12. FAST/SLOW PATH: compressed vs expanded metadata
13. LLM / PROBABILISTIC REASONING: constrained generation
14. OKA / BEHAVIORAL ENCRYPTION: cross-domain knowledge, encryption
15. MACHINE B VALIDATOR: deterministic verification
16. MEMORY UPDATE: state persistence
17. MG8 / G8SON CONTAINER ASSEMBLY: gate constraints, containerization
18. EVIDENCE EMISSION: canonical QSON-compatible events
19. PACKAGE/RETURN: expose result
"""

from nych.pipeline import PipelineConfig, run_pipeline
from nych.types import (
    AuditUnit,
    CandidateTransform,
    CognitiveOperator,
    CompetencyLevel,
    ControlOperator,
    InputType,
    Modality,
    NaturalLanguageInput,
    NychContext,
    NychPacket,
    NychState,
    NYCHPipelineResult,
    Perspective,
    SensorInput,
    SourceType,
    Tense,
    ValidationResult,
)
from nych.gates import (
    ActionPermit,
    GateDefinition,
    GateInstance,
    GateOutcome,
    GateState,
    MGateOrchestrator,
    ThreeGateSet,
)

__version__ = "1.2.0"
__all__ = [
    "run_pipeline",
    "PipelineConfig",
    "AuditUnit",
    "CandidateTransform",
    "CognitiveOperator",
    "CompetencyLevel",
    "ControlOperator",
    "InputType",
    "Modality",
    "NaturalLanguageInput",
    "NychContext",
    "NychPacket",
    "NychState",
    "NYCHPipelineResult",
    "Perspective",
    "SensorInput",
    "SourceType",
    "Tense",
    "ValidationResult",
    "ActionPermit",
    "GateDefinition",
    "GateInstance",
    "GateOutcome",
    "GateState",
    "MGateOrchestrator",
    "ThreeGateSet",
]
