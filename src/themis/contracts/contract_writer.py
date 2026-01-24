from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def write_contract_yaml(contract: Dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(contract, sort_keys=False, allow_unicode=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path
