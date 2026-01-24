from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

"""
------------------------------------------------------------------------------------------
RuleResult:

- checks one rule outcome (checks if rule has passed, its severity, and additional
details such as which columns failed and the number of rows assocated with the rule
failure)

ValidationRun:

- Whole run summary: dataset name, total rows, ERROR rule failures, list all rule
results, reason for quarantine 

------------------------------------------------------------------------------------------
"""

@dataclass
class RuleResult:
    rule: str
    severity: str  
    passed: bool
    details: Dict[str, Any]

@dataclass
class ValidationRun:
    dataset_name: str
    total_rows: int
    error_failed: bool
    rule_results: List[RuleResult]
    quarantine_reason_col: str = "__themis_error_reasons__"
