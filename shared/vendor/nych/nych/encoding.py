"""
NYCH Encoding

Handles translation between symbol sequences and address traces.
"""

from typing import List, Tuple

from .symbols import Symbol
from .addressing import extend_address


def encode_sequence(
    symbols: List[Symbol],
    base_address: Tuple[float, ...],
) -> List[Tuple[str, Tuple[float, ...]]]:
    """
    Encode a sequence of symbols into address space by appending
    ordinal position as an emergent dimension.

    Symbols are immutable in the current model, so encoding produces a
    derived address trace rather than mutating each Symbol in place.
    """
    encoded = []
    for i, sym in enumerate(symbols):
        addr = extend_address(base_address, float(i))
        encoded.append((sym.glyph, addr))
    return encoded


def decode_sequence(encoded):
    """Strip addresses and return the glyph sequence."""
    return [glyph for glyph, _ in encoded]
