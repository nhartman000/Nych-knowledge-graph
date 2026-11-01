"""
NYCH VS Code Bridge

Invoked by VS Code extension via subprocess.
"""

import json
import sys


def main() -> int:
    """Reserved subprocess entry point for the future VS Code bridge.

    The previous tracked file ended with an incomplete import and made the
    package syntactically invalid. Keep this bridge explicit and inert until
    its request/response contract is defined.
    """
    json.dump({"status": "not_implemented"}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
