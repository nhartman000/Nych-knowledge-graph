"""
NYCH Domain Expansion Module
============================
Domain -> Discipline -> Function -> Technique -> TOTE candidate loops.
DOTM (Domain of the Machine) Cataloging: Tools / Instruments Identified in Domain.
Spatial Modeling + Field of Data x Influence = DOMAIN.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nych.types import NychContext, NychPacket, NychState

# Global TOTE loop database instance
_tote_db = None


def get_tote_db() -> Any:
    """Get the global TOTE loop database instance."""
    global _tote_db
    if _tote_db is None:
        from nych.tote_db import TOTELoopDatabase
        _tote_db = TOTELoopDatabase()
    return _tote_db


@dataclass(frozen=True)
class DomainExpansion:
    """Result of domain expansion."""
    domain: str
    discipline: str
    function: str
    technique: str
    tote_candidates: list[dict[str, Any]] = field(default_factory=list)
    expansion_path: list[str] = field(default_factory=list)
    dotm_tools: list[str] = field(default_factory=list)
    dotm_instruments: list[str] = field(default_factory=list)
    specialties: list[str] = field(default_factory=list)
    subdomains: list[str] = field(default_factory=list)


# Canonical domain ontology: Domain -> Discipline -> Function -> Technique
_DOMAIN_ONTOLOGY: dict[str, dict[str, Any]] = {
    "programming": {
        "disciplines": ["software_engineering", "data_engineering", "devops"],
        "functions": ["develop", "test", "deploy", "maintain", "design"],
        "techniques": {
            "develop": ["tdd", "pair_programming", "code_review", "refactoring"],
            "test": ["unit_testing", "integration_testing", "e2e_testing", "mutation_testing"],
            "deploy": ["ci_cd", "blue_green", "canary", "docker_compose"],
            "maintain": ["refactoring", "debugging", "monitoring", "profiling"],
            "design": ["uml", "architecture_patterns", "solid_principles", "api_design"],
        },
        "specialties": ["frontend", "backend", "fullstack", "embedded", "security"],
        "subdomains": ["web", "mobile", "cloud", "desktop", "systems"],
        "tools": ["compiler", "interpreter", "debugger", "linter", "ide", "version_control"],
        "instruments": ["profiler", "tracer", "coverage_tool", "static_analyzer"],
    },
    "medical": {
        "disciplines": ["clinical_practice", "surgery", "radiology", "pharmacy"],
        "functions": ["diagnose", "treat", "monitor", "prevent", "research"],
        "techniques": {
            "diagnose": ["physical_exam", "lab_test", "imaging", "differential_diagnosis"],
            "treat": ["medication", "surgery", "therapy", "lifestyle_change"],
            "monitor": ["vitals", "blood_test", "imaging_followup", "wearable"],
            "prevent": ["vaccination", "screening", "counseling", "public_health"],
            "research": ["clinical_trial", "case_study", "meta_analysis", "epidemiology"],
        },
        "specialties": ["cardiology", "neurology", "orthopedics", "pediatrics", "oncology"],
        "subdomains": ["emergency", "outpatient", "inpatient", "icu", "lab"],
        "tools": ["stethoscope", "syringe", "scalpel", "monitor", "xray"],
        "instruments": ["ecg", "mri", "ct_scanner", "microscope", "centrifuge"],
    },
    "construction": {
        "disciplines": ["carpentry", "masonry", "electrical", "plumbing", "architecture"],
        "functions": ["measure", "cut", "assemble", "finish", "inspect"],
        "techniques": {
            "measure": ["tape_measure", "laser_level", "square", "compass"],
            "cut": ["saw", "chisel", "router", "laser_cutter"],
            "assemble": ["nail", "screw", "glue", "weld", "bolt"],
            "finish": ["sand", "paint", "stain", "varnish", "plaster"],
            "inspect": ["visual_check", "level", "moisture_meter", "code_verify"],
        },
        "specialties": ["framing", "roofing", "flooring", "drywall", "painting"],
        "subdomains": ["residential", "commercial", "industrial", "infrastructure"],
        "tools": ["hammer", "saw", "drill", "level", "tape_measure", "wrench"],
        "instruments": ["blueprint", "calculator", "angle_finder", "square"],
    },
    "data_processing": {
        "disciplines": ["data_analysis", "data_engineering", "data_science", "bi"],
        "functions": ["collect", "transform", "analyze", "visualize", "store"],
        "techniques": {
            "collect": ["api_ingestion", "batch_import", "streaming", "web_scraping"],
            "transform": ["cleaning", "normalization", "aggregation", "pivot"],
            "analyze": ["statistical", "ml_inference", "rule_based", "anomaly_detection"],
            "visualize": ["charts", "dashboards", "reports", "heatmaps"],
            "store": ["database", "data_lake", "warehouse", "cache"],
        },
        "specialties": ["etl", "sql", "python", "spark", "airflow"],
        "subdomains": ["batch", "streaming", "real_time", "historical"],
        "tools": ["jupyter", "pandas", "spark", "sql_client", "etl_tool"],
        "instruments": ["profiler", "data_catalog", "quality_scanner", "lineage_tracker"],
    },
    "testing": {
        "disciplines": ["qa", "automation", "performance", "security"],
        "functions": ["plan", "design", "execute", "report", "improve"],
        "techniques": {
            "plan": ["test_strategy", "coverage_analysis", "risk_assessment"],
            "design": ["test_cases", "test_data", "environment_setup"],
            "execute": ["automated", "manual", "exploratory", "regression"],
            "report": ["metrics", "coverage", "defect_tracking", "dashboard"],
            "improve": ["refactor_tests", "flaky_fix", "cicompliance"],
        },
        "specialties": ["unit", "integration", "e2e", "load", "security"],
        "subdomains": ["frontend", "backend", "api", "mobile", "infra"],
        "tools": ["test_runner", "coverage_tool", "mock_framework", "ci_pipeline"],
        "instruments": ["assertion_library", "snapshot_tool", "log_analyzer", "profiler"],
    },
    "legal": {
        "disciplines": ["litigation", "corporate", "intellectual_property", "criminal"],
        "functions": ["research", "draft", "review", "argue", "settle"],
        "techniques": {
            "research": ["case_law", "statute", "precedent", "discovery"],
            "draft": ["contract", "motion", "pleading", "opinion"],
            "review": ["due_diligence", "compliance", "redline", "edit"],
            "argue": ["brief", "oral_argument", "cross_examine", "objection"],
            "settle": ["negotiation", "mediation", "arbitration", "plea_bargain"],
        },
        "specialties": ["corporate", "criminal", "family", "immigration", "tax"],
        "subdomains": ["civil", "criminal", "administrative", "appellate"],
        "tools": ["legal_db", "document_manager", "contract_analyzer", "calendar"],
        "instruments": ["precedent_finder", "statute_tracker", "citation_checker"],
    },
    "finance": {
        "disciplines": ["accounting", "investment", "banking", "insurance", "audit"],
        "functions": ["record", "analyze", "forecast", "comply", "invest"],
        "techniques": {
            "record": ["bookkeeping", "ledger", "invoice", "receipt"],
            "analyze": ["ratio_analysis", "trend", "variance", "benchmark"],
            "forecast": ["budget", "cash_flow", "scenario", "model"],
            "comply": ["audit", "reporting", "regulatory", "tax"],
            "invest": ["portfolio", "asset_allocation", "risk", "return"],
        },
        "specialties": ["cpa", "cfa", "cfp", "actuarial", "compliance"],
        "subdomains": ["corporate", "personal", "public", "nonprofit"],
        "tools": ["accounting_software", "spreadsheet", "trading_platform", "risk_model"],
        "instruments": ["financial_statements", "ratios", "valuation_model", "audit_trail"],
    },
    "unknown": {
        "disciplines": ["general"],
        "functions": ["process"],
        "techniques": {
            "process": ["generic_workflow"],
        },
        "specialties": ["general"],
        "subdomains": ["general"],
        "tools": ["generic_tool"],
        "instruments": ["generic_instrument"],
    },
}


def expand_domain(
    packet: NychPacket,
    context: NychContext,
    state: NychState,
) -> DomainExpansion:
    """
    Expand domain into discipline, function, technique, and TOTE candidates.
    Also catalog DOTM (Domain of the Machine) tools and instruments.
    
    Spatial Modeling + Field of Data x Influence = DOMAIN
    
    Args:
        packet: The current NYCH packet.
        context: The current NYCH context.
        state: The current NYCH state.
    
    Returns:
        DomainExpansion with expanded domain path and TOTE candidates.
    """
    domain = context.domain
    ontology = _DOMAIN_ONTOLOGY.get(domain, _DOMAIN_ONTOLOGY["unknown"])
    
    # Select discipline (first match for determinism)
    discipline = ontology["disciplines"][0] if ontology["disciplines"] else "general"
    
    # Select function based on intent
    intent = context.intent
    functions = ontology.get("functions", ["process"])
    function = _select_function(intent, functions)
    
    # Select technique based on function
    techniques = ontology.get("techniques", {}).get(function, ["generic_workflow"])
    technique = techniques[0] if techniques else "generic_workflow"
    
    # Catalog DOTM tools and instruments
    dotm_tools = ontology.get("tools", ["generic_tool"])
    dotm_instruments = ontology.get("instruments", ["generic_instrument"])
    specialties = ontology.get("specialties", ["general"])
    subdomains = ontology.get("subdomains", ["general"])
    
    # Generate TOTE candidates from hierarchical domain database
    tote_candidates = _generate_tote_candidates(
        domain, discipline, function, technique, context.competency
    )
    
    # Try to fetch from TOTE loop database (nhartman000/TOTE-loops)
    try:
        tote_db = get_tote_db()
        db_record = tote_db.fetch_tote_loop(domain, function, technique)
        if db_record:
            # Augment with database record if available
            tote_candidates.insert(0, {
                "tote_id": db_record.tote_id,
                "domain": db_record.domain,
                "discipline": db_record.discipline,
                "function": db_record.function,
                "technique": db_record.technique,
                "test_condition": db_record.test_condition,
                "operate_action": db_record.operate_action,
                "exit_condition": db_record.exit_condition,
                "object_actor_action": db_record.object_actor_action,
                "max_iterations": db_record.max_iterations,
                "admissibility_score": db_record.efficacy_score,
                "competency_match": db_record.competency_required,
                "tools_required": db_record.tools_required,
                "source": "tote_db",
            })
    except Exception:
        pass  # TOTE DB lookup is optional
    
    expansion_path = [domain, discipline, function, technique]
    
    return DomainExpansion(
        domain=domain,
        discipline=discipline,
        function=function,
        technique=technique,
        tote_candidates=tote_candidates,
        expansion_path=expansion_path,
        dotm_tools=dotm_tools,
        dotm_instruments=dotm_instruments,
        specialties=specialties,
        subdomains=subdomains,
    )


def _select_function(intent: str, functions: list[str]) -> str:
    """Select function based on intent."""
    intent_function_map = {
        "imagine": "design",
        "compare": "analyze",
        "remember": "collect",
        "evaluate": "test",
        "iterate": "process",
        "test": "test",
        "operate": "process",
        "process": "process",
        "diagnose": "diagnose",
        "treat": "treat",
        "monitor": "monitor",
        "prevent": "prevent",
        "research": "research",
        "measure": "measure",
        "cut": "cut",
        "assemble": "assemble",
        "finish": "finish",
        "inspect": "inspect",
        "collect": "collect",
        "transform": "transform",
        "analyze": "analyze",
        "visualize": "visualize",
        "store": "store",
        "plan": "plan",
        "design": "design",
        "execute": "execute",
        "report": "report",
        "improve": "improve",
        "record": "record",
        "forecast": "forecast",
        "comply": "comply",
        "invest": "invest",
        "research": "research",
        "draft": "draft",
        "review": "review",
        "argue": "argue",
        "settle": "settle",
    }
    
    mapped = intent_function_map.get(intent)
    if mapped and mapped in functions:
        return mapped
    
    return functions[0]


def _generate_tote_candidates(
    domain: str,
    discipline: str,
    function: str,
    technique: str,
    competency: str,
) -> list[dict[str, Any]]:
    """
    Generate TOTE candidate loops for the given domain path.
    
    TOTE = Test, Operate, Test, Exit
    
    Each candidate is a TOTE loop specification that terminates as
    Object-Actor-Action loops.
    """
    candidates = []
    
    # Generate a deterministic set of TOTE candidates
    for i in range(3):  # Up to 3 candidates for determinism
        candidate = {
            "tote_id": f"tote_{domain}_{discipline}_{function}_{technique}_{i}",
            "domain": domain,
            "discipline": discipline,
            "function": function,
            "technique": technique,
            "test_condition": f"test_{function}_{i}",
            "operate_action": f"operate_{technique}_{i}",
            "exit_condition": f"exit_{function}_{i}",
            "object_actor_action": f"{function}_{technique}_loop",
            "max_iterations": 10,
            "admissibility_score": 1.0 - (i * 0.1),  # Deterministic scoring
            "competency_match": competency,
        }
        candidates.append(candidate)
    
    return candidates


def get_domain_ontology() -> dict[str, dict[str, Any]]:
    """Get the canonical domain ontology."""
    return _DOMAIN_ONTOLOGY
