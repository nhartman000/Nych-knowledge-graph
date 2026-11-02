#!/usr/bin/env bash
# SHA256 of every tracked file (inputs, code, outputs) except the manifest itself.
cd "$(dirname "$0")/../.." && git ls-files | grep -v '^REVIEW/MANIFEST.sha256$' | xargs -d '\n' sha256sum > REVIEW/MANIFEST.sha256 && wc -l REVIEW/MANIFEST.sha256
