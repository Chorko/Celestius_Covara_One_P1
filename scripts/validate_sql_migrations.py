"""Validate SQL migration naming and ordering safety guardrails."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "backend" / "sql"
FILE_PATTERN = re.compile(r"^(?P<version>\d{2})_[a-z0-9_]+\.sql$", re.IGNORECASE)


def main() -> int:
    if not SQL_DIR.exists():
        print(f"ERROR: SQL directory not found: {SQL_DIR}")
        return 1

    files = sorted(SQL_DIR.glob("*.sql"))
    if not files:
        print("ERROR: No SQL migration files found under backend/sql.")
        return 1

    seen_versions: dict[int, str] = {}

    for path in files:
        match = FILE_PATTERN.match(path.name)
        if not match:
            print(
                "ERROR: Migration file does not match required pattern "
                f"NN_description.sql: {path.name}"
            )
            return 1

        version = int(match.group("version"))
        if version in seen_versions:
            print(
                "ERROR: Duplicate migration version prefix "
                f"{version:02d} in {seen_versions[version]} and {path.name}."
            )
            return 1

        contents = path.read_text(encoding="utf-8").strip()
        if not contents:
            print(f"ERROR: Migration file is empty: {path.name}")
            return 1

        seen_versions[version] = path.name

    if 0 not in seen_versions:
        print("ERROR: Missing base migration 00_*.sql.")
        return 1

    versions = list(seen_versions.keys())
    if versions != sorted(versions):
        print("ERROR: Migration files are not ordered by numeric prefix.")
        return 1

    print(
        "SQL migration guardrails passed for "
        f"{len(files)} files (base={min(versions):02d}, latest={max(versions):02d})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
