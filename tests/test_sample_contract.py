from pathlib import Path
import yaml

from themis.contracts.infer_contract import infer_contract_from_path


def test_sample_contract_ranges_are_suggested_not_enforced(tmp_path: Path):
    contract = infer_contract_from_path(
        Path("examples/data/fct_observations_bad.csv"),
        range_mode="p01p99",
    )

    # numeric cols should use suggested_* keys, not min/max
    cols = {c["name"]: c for c in contract["columns"]}

    t2m = cols["t2m_c"]
    assert "suggested_min" in t2m and "suggested_max" in t2m
    assert "min" not in t2m and "max" not in t2m

    # ensure suggested values look like interior bounds (not extremes)
    assert t2m["suggested_min"] == 4.2
    assert t2m["suggested_max"] == 5.0

    # ensure ts is detected as datetime
    assert cols["ts"]["dtype"] == "datetime"

    # ensure PK stays empty (as default)
    assert contract["primary_key"] == []
