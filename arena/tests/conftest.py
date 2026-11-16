# ABOUTME: Path setup so Arena tests run without an installed package.
# ABOUTME: Puts the repo root and the arena directory on sys.path.

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ARENA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (_REPO_ROOT, _ARENA_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)
