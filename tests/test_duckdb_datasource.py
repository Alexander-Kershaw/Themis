from pathlib import Path
import duckdb
import polars as pl

from themis.datasources.factory import make_datasource
from themis.contracts.loader import load_contract
from themis.validate.validator import validate


def test_duckdb_datasource_roundtrip(tmp_path: Path):
    # Builds a small duckdb with a table
    db_path = tmp_path / "demo.db"
    con = duckdb.connect(str(db_path))
    con = duckdb.connect(str(db_path))

    con.execute("""
    create table t (
      station_id varchar,
      ts varchar,
      t2m_c double,
      wind_ms double
    )
    """)

    con.execute("""
    insert into t values
      ('ABCD','2026-01-01T00:00:00Z', 4.2, 7.1),
      ('EFGH','2026-01-01T01:00:00Z', 999.0, 5.0)
    """)
    con.close()

    # Create datasource from uri
    uri = f"duckdb:///{db_path}?query=select%20*%20from%20t"
    ds = make_datasource(uri)
    df = ds.read()

    assert isinstance(df, pl.DataFrame)
    assert df.height == 2
    assert set(df.columns) >= {"station_id", "ts", "t2m_c", "wind_ms"}

    # Validate using existing example contract
    contract = load_contract(Path("contracts/examples/fct_observations.yml"))
    run, clean, quar = validate(df, contract)

    assert run.dataset_name == "fct_observations"
    assert quar.height == 1
    assert "ranges" in quar["__themis_error_reasons__"].to_list()[0]
