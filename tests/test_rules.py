from themis.validate.validator import validate
import polars as pl

"""
------------------------------------------------------------------------------------------------
Testing rules:
------------------------------------------------------------------------------------------------
This testing script motivates the following testing aspects:

- Missing required columns (schema test) -> quarantine all with missing_required_columns
    in the reason vector

- Null vales in required fields -> quarantined only rows effected with nulls

- Duplicate primary keys -> quarantine the duplicated rows

- Range issues -> quarantine values violating range constrant rules

- Regex warn -> Annotated but not quarantined
------------------------------------------------------------------------------------------------
"""


BASE_CONTRACT = {
    "dataset_name": "fct_observations",
    "primary_key": ["station_id", "ts"],
    "columns": [
        {"name": "station_id", "dtype": "string", "required": True, "regex": "^[A-Z]{4}$"},
        {"name": "ts", "dtype": "datetime", "required": True},
        {"name": "t2m_c", "dtype": "float", "required": True, "min": -50, "max": 60},
        {"name": "wind_ms", "dtype": "float", "required": False, "min": 0, "max": 80},
    ],
    "rules": {
        "uniqueness": ["station_id", "ts"],
        "not_null": ["station_id", "ts", "t2m_c"],
    },
    "severity": {
        "schema_required_columns": "error",
        "uniqueness": "error",
        "not_null": "error",
        "ranges": "error",
        "regex": "warn",
        "allowed_values": "error",
    },
}


def test_schema_missing_required_column_quarantines_all():
    df = pl.DataFrame(
        {
            "station_id": ["ABCD", "EFGH"],
            "t2m_c": [4.2, 3.1],
            "wind_ms": [7.1, 5.2]
        }
    )

    run, clean, quar = validate(df, dict(BASE_CONTRACT))

    assert run.error_failed is True
    assert clean.height == 0
    assert quar.height == 2
    assert "__themis_error_reasons__" in quar.columns
    assert quar["__themis_error_reasons__"].unique().to_list() == ["missing_required_columns"]


def test_not_null_quarantines_only_failing_rows():
    df = pl.DataFrame(
        {
            "station_id": ["ABCD", "EFGH", "IJKL"],
            "ts": ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z", "2026-01-01T02:00:00Z"],
            "t2m_c": [4.2, None, 2.0],
            "wind_ms": [7.1, 5.2, 6.0],
        }
    )

    run, clean, quar = validate(df, dict(BASE_CONTRACT))

    assert run.error_failed is True
    assert clean.height == 2
    assert quar.height == 1
    assert quar["__themis_error_reasons__"].to_list() == ["not_null"]


def test_uniqueness_quarantines_duplicate_pk_rows():
    df = pl.DataFrame(
        {
            "station_id": ["ABCD", "ABCD", "EFGH"],
            "ts": ["2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"],
            "t2m_c": [4.2, 4.2, 3.0],
            "wind_ms": [7.1, 7.1, 5.0],
        }
    )

    run, clean, quar = validate(df, dict(BASE_CONTRACT))

    assert run.error_failed is True
    assert quar.height == 2
    assert all("uniqueness" in s for s in quar["__themis_error_reasons__"].to_list())


def test_ranges_quarantines_out_of_range_rows():
    df = pl.DataFrame(
        {
            "station_id": ["ABCD", "EFGH", "IJKL"],
            "ts": ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z", "2026-01-01T02:00:00Z"],
            "t2m_c": [4.2, 999.0, 2.0],
            "wind_ms": [7.1, 5.0, -3.0],
        }
    )

    run, clean, quar = validate(df, dict(BASE_CONTRACT))

    assert run.error_failed is True
    assert clean.height == 1
    assert quar.height == 2
    assert all("ranges" in s for s in quar["__themis_error_reasons__"].to_list())


def test_regex_warn_does_not_quarantine():
    df = pl.DataFrame(
        {
            "station_id": ["ABCD", "abc"],  # second fails regex
            "ts": ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"],
            "t2m_c": [4.2, 5.0],
            "wind_ms": [7.1, 6.8],
        }
    )

    run, clean, quar = validate(df, dict(BASE_CONTRACT))

    assert run.error_failed is False
    assert quar.height == 0
    assert clean.height == 2
    assert clean["__themis_warn_reasons__"].to_list() == ["", "regex"]


def test_allowed_values_quarantines_invalid_values():
    contract = dict(BASE_CONTRACT)
    contract["columns"] = [
        {**c, "allowed_values": ["ABCD", "EFGH"]} if c["name"] == "station_id" else c
        for c in contract["columns"]
    ]

    df = pl.DataFrame(
        {
            "station_id": ["ABCD", "WXYZ"],
            "ts": ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"],
            "t2m_c": [4.2, 5.0],
            "wind_ms": [7.1, 6.8],
        }
    )

    run, clean, quar = validate(df, contract)

    assert run.error_failed is True
    assert clean.height == 1
    assert quar.height == 1
    assert "allowed_values" in quar["__themis_error_reasons__"].to_list()[0]
