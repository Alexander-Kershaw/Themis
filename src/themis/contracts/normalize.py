from __future__ import annotations

from typing import Any, Dict, List

# For normalizing contract structures so the validator can access column metadata easily
def normalize_contract(raw: Dict[str, Any]) -> Dict[str, Any]:
    c = dict(raw)

    # primary_key is always list
    pk = c.get("primary_key") or []
    if isinstance(pk, str):
        pk = [pk]
    c["primary_key"] = list(pk)

    # columns is always list of dicts
    cols = c.get("columns") or []
    if not isinstance(cols, list):
        raise ValueError("columns must be a list")
    c["columns"] = cols

    # rules are always dict
    rules = c.get("rules") or {}
    if not isinstance(rules, dict):
        raise ValueError("rules must be a mapping")
    c["rules"] = rules

    # severity is always dict, lowercase values
    sev = c.get("severity") or {}
    if not isinstance(sev, dict):
        raise ValueError("severity must be a mapping")
    c["severity"] = {str(k): str(v).lower() for k, v in sev.items()}

    return c


def columns_by_name(contract: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for col in contract.get("columns", []):
        name = col.get("name")
        if name:
            out[str(name)] = dict(col)
    return out


def required_columns(contract: Dict[str, Any]) -> List[str]:
    req = []
    for col in contract.get("columns", []):
        if col.get("required") is True and col.get("name"):
            req.append(str(col["name"]))
    return req
