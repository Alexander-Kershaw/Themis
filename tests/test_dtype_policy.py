import polars as pl

from themis.contracts.loader import load_contract
from themis.validate.validator import validate
from pathlib import Path

def test_dtype_error_mode_quarantines_all_without_coercion():
    contract = load_contract(Path("contracts/examples/fct_observations.yml"))

    df = pl.DataFrame(
        {
            "station_id": ["ABCD", "EFGH"],
            "ts": ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"], 
            "t2m_c": [4.2, 5.0],
            "wind_ms": [7.1, 6.8],
        }
    )

    run, clean, quar = validate(df, contract, dtype_mode="error", coerce_dtypes=False)
    assert run.error_failed is True
    assert clean.height == 0
    assert quar.height == 2
    assert quar["__themis_error_reasons__"].unique().to_list() == ["schema_dtypes"]


def test_dtype_error_mode_passes_with_coercion_for_datetime():
    contract = load_contract(Path("contracts/examples/fct_observations.yml"))

    df = pl.DataFrame(
        {
            "station_id": ["ABCD", "EFGH"],
            "ts": ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"],
            "t2m_c": [4.2, 5.0],
            "wind_ms": [7.1, 6.8],
        }
    )

    run, clean, quar = validate(df, contract, dtype_mode="error", coerce_dtypes=True)
    assert run.error_failed is False
    assert quar.height == 0
    assert clean.height == 2
    assert str(clean["ts"].dtype).lower().startswith("datetime")
