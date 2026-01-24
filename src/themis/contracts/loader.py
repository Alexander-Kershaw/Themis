from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

# Load data contract (to check input csv/parquet against)
def load_contract(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Contract not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Contract YAML must parse to a mapping/object at the top level")

    if "dataset_name" not in data:
        raise ValueError("Contract missing required field: dataset_name")
    if "columns" not in data:
        raise ValueError("Contract missing required field: columns")

    return data
