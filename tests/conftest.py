from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = REPO_ROOT / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(relative: str):
    return json.loads((FIXTURES / relative).read_text(encoding="utf-8"))
