"""Generate backend OpenAPI contract from the live FastAPI app.

Usage:
    d:/Celestius_DEVTrails_P1/.venv/Scripts/python.exe scripts/generate_openapi.py
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app


def main() -> None:
    spec = app.openapi()
    output_path = ROOT / "backend" / "openapi.yaml"
    output_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote OpenAPI contract to {output_path}")


if __name__ == "__main__":
    main()
