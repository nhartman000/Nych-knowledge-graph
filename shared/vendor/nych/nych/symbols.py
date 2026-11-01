from dataclasses import dataclass
from typing import Tuple, Any

AddressTuple = Tuple[float, float, float, float]

@dataclass(frozen=True)
class Symbol:
    glyph: str
    meaning: str
    address: AddressTuple
    metadata: Any = None
