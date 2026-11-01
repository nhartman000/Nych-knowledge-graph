"""
Physical + Logical storage binding

Each symbol maps to:
- a deterministic address
- an assignable physical sector reference
"""

class SymbolStorage:
    def __init__(self):
        self._store = {}

    def bind(self, symbol, physical_offset: int):
        self._store[symbol] = physical_offset

    def locate(self, symbol):
        return self._store.get(symbol)

    def delete(self, symbol):
        if symbol in self._store:
            del self._store[symbol]
