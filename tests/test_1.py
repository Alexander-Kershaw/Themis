from pathlib import Path
import polars as pl

from themis.contracts.loader import load_contract
from themis.validate.validator import validate


def test_validate_runs_on_example_contract():
    contract = load_contract(Path("contracts/examples/fct_observations.yml"))
    df = pl.read_csv("examples/data/fct_observations_bad.csv")

    run, clean, quar = validate(df, contract)

    assert run.dataset_name == "fct_observations"
    assert clean.height == 2
    assert quar.height == 2
    assert run.error_failed is True
