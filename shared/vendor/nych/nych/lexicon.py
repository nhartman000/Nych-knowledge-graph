from nych.symbols import Symbol
from nych.addressing import root_address

# Temporary boot lexicon
# This exists ONLY to satisfy engine contracts.
# Your real NYCH lexicon will replace this later via loaders.

LEXICON = {
    "👁️": Symbol(
        glyph="👁️",
        meaning="perception",
        address=root_address(),
    ),
    "🤝": Symbol(
        glyph="🤝",
        meaning="cooperation",
        address=root_address(),
    ),
    "⚖️": Symbol(
        glyph="⚖️",
        meaning="stability",
        address=root_address(),
    ),
    "🤷": Symbol(
        glyph="🤷",
        meaning="uncertainty",
        address=root_address(),
    ),
}
