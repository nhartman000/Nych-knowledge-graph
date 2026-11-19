from .common import BASES, CHECK_TYPES

CHECKLIST_SCHEMA = {
    "type": "object",
    "required": ["steps"],
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["step_id", "source_lines", "source_quote", "tote", "exit_checks"],
                "properties": {
                    "step_id": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_-]{0,31}$"},
                    "source_lines": {"type": "array", "minItems": 1, "items": {"type": "integer", "minimum": 1}},
                    "source_quote": {"type": "string", "minLength": 1},
                    "tote": {
                        "type": "object",
                        "required": ["operate", "exit"],
                        "properties": {"initial_test": {"type": "string"}, "operate": {"type": "string"},
                                       "exit": {"type": "string"}, "max_iterations": {"type": "integer"}},
                    },
                    "exit_checks": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["type", "params", "basis"],
                            "properties": {
                                "type": {"enum": list(CHECK_TYPES)},
                                "params": {"type": "object"},
                                "basis": {"enum": list(BASES)},
                            },
                        },
                    },
                },
            },
        }
    },
}
