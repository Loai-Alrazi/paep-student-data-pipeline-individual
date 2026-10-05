"""Seed the learning MongoDB source collection from the tracked JSON fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.output.mongodb_writer import write_mongodb  # noqa: E402
from app.utils.config_loader import load_config  # noqa: E402


def main() -> None:
    config = load_config()
    source_config = config["sources"]["mongodb"]
    fixture_path = ROOT / "data" / "raw" / "mongodb_students.json"
    records = json.loads(fixture_path.read_text(encoding="utf-8"))
    write_mongodb(pd.DataFrame.from_records(records), source_config)
    print(
        f"Seeded {len(records)} documents into "
        f"{source_config['database']}.{source_config['collection']}"
    )


if __name__ == "__main__":
    main()
