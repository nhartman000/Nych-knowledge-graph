from typing import Tuple
import time

AddressTuple = Tuple[float, float, float, float]
ExtendedAddress = Tuple[float, ...]


def root_address() -> AddressTuple:
    return (0.0, 0.0, 0.0, 0.0)


def make_address(
    *,
    region: float = 0.0,
    volume: float = 0.0,
    context: float = 0.0,
    t: float | None = None,
) -> AddressTuple:
    if t is None:
        t = time.time()
    return (t, region, volume, context)


def extend_address(base_address: Tuple[float, ...], value: float) -> ExtendedAddress:
    """Append one emergent dimension without mutating the original address."""
    return tuple(float(component) for component in base_address) + (float(value),)
