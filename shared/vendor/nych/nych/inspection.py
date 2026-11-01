"""
Inspection / Oversight layer

Used for:
- audit
- quarantine
- deletion
"""

class Inspector:
    def __init__(self, storage):
        self.storage = storage

    def inspect(self, symbol):
        return {
            "symbol": symbol,
            "address": symbol.address,
            "physical": self.storage.locate(symbol),
        }

    def quarantine(self, symbol):
        self.storage.delete(symbol)

