***
# Themis
***
**Engine-agnostic Data Contracts, Quality Gates, and Quarantine**

Themis is designed to be reusable validation framework for enforcing **data contracts** before datasets are allowed to enter **silver/gold** layers. It validates schema and rule constraints, splits data into **clean vs quarantine**, and generates **comprehensive reports** for debugging and audit trails.

Themis is designed to be reusable across other projects (warehouses, streaming pipelines, analytics engineering stacks), and I intend to incorporate it in future projects workflows.

---

## What Themis Does

**When provided with:**
- an input dataset (CSV/ Parquet, and optional DuckDB query)
- a YAML data contract that defines schema and rules

**Themis will:**
- validate the dataset against the YAML contract
- partition data into:
    - 'clean/' (given all ERROR-level rules are passed)
    - 'quarantine/' (failure of at least on ERROR-level rule)
- generate data report:
    - JSON report
    - Markdown report
- return meaningful exit codes (for CI/ GitHub Actions)

---

## Features

### Validation Phases
Validates against contract definition in YAML.

1. **Schema validation**
   - Required columns exist
   - Types are compatible (and dtype coersion)

2. **Row validation**
   - Not-null constraints
   - Numeric ranges
   - Allowed values
   - Regex pattern rules (warn or error)

3. **Table validation**
   - Uniqueness (primary key)

---

### Quarantine Pattern
When validation fails, the dataset is split into:

- `clean/`  
  Rows that pass **all ERROR-level rules**

- `quarantine/`  
  Rows that fail **any ERROR-level rule**

**WARN-level rules do not quarantine.**  
They annotate and appear in reports, but the row can still pass through.

---

### Reporting
Every validation run creates both JSON and Markdown reports:

- `reports/<dataset>/<run_id>.json`
- `reports/<dataset>/<run_id>.md`

Reports include:

- Counts: total / clean / quarantined
- Rule results (pass/fail, severity)
- Top failing examples (first N bad rows)
- Basic column summary stats

---

### Inputs
Themis is engine-agnostic and accepts:

- CSV
- Parquet
- DuckDB query

---

## Repository Layout

```text

├── README.md
├── contracts
│   ├── examples
│   │   └── fct_observations.yml
│   ├── generated
│   │   └── fct_observations_bad.yml
│   └── data
│       ├── fct_observations.csv
│       ├── fct_observations_bad.csv
│       ├── out
│       └── themis_demo.db
├── pyproject.toml
├── src
│   ├── themis
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── contracts
│   │   ├── datasources
│   │   ├── quarantine
│   │   ├── reporting
│   │   └── validate
└── tests
    ├── _helpers.py
    ├── test_1.py
    ├── test_dtype_policy.py
    ├── test_duckdb_datasource.py
    ├── test_rules.py
    └── test_sample_contract.py

```

---

## Install

**Recommended:** Local dev install

```bash
python -m pip install -U pip
pip install -e ".[dev]"
```

**Optional:** DuckDB support if you want to validate query results

```bash
pip install -e ".[duckdb]"
```

---

## Quick Start

To validate a dataset against a contract:

```bash
themis validate \
  --contract contracts/examples/fct_observations.yml \
  --input examples/data/fct_observations.csv \
  --out out_run/
```

Outputs:

```text
out_run/
  clean/data.parquet
  quarantine/data.parquet
  reports/<dataset>/<run_id>.json
  reports/<dataset>/<run_id>.md
  run_summary.txt
```

---

## CLI Commands

```bash
themis validate --contract <contract.yml> --input <data.csv|data.parquet|duckdb://...> --out <out_dir>
```

**Exit Codes:**

- 0 = passed all ERROR-level rules
- 2 = has at least one ERROR-level rule failure (quarantined)
- 1 = runtime error (bad contract, unreadable input, etc.)

---

## Contract Format (YAML)

**Example Contract:** contracts/examples/fct_observations.yml

```yaml
dataset_name: fct_observations
primary_key: [station_id, ts]

columns:
  - name: station_id
    dtype: string
    required: true
    regex: "^[A-Z]{4}$"

  - name: ts
    dtype: datetime
    required: true

  - name: t2m_c
    dtype: float
    required: true
    min: -50
    max: 60

  - name: wind_ms
    dtype: float
    required: false
    min: 0
    max: 80

rules:
  uniqueness: [station_id, ts]
  not_null: [station_id, ts, t2m_c]

severity:
  uniqueness: error
  not_null: error
  ranges: error
  regex: warn
```

---

## Supported Rules

### Schema Rules

- Required columns (`schema_required_columns`)
- Dtype policy (`schema_dtypes`) (is optional)

### Row Rules

- `not_null`: columns that must never be null
- `ranges`: numeric min/max checks
- `allowed_values`: enum values
- `regex`: string pattern match

### Table Rules

- `uniqueness`: primary key uniqueness

---

## Quarantine Behaviour

### ERROR severity

- row is moved into `quarantine/`
- row receives `__themis_warn_reasons__` set to the rule names

### WARN severity

- row remains in `clean/`
- the row obtains `__themis_warn_reasons__` set to the rule names

---

## Reports

**Themis writes reports in:**

- `reports/<dataset>/<run_id>.json`
- `reports/<dataset>/<run_id>.md`

**Reports include:**

- total/clean/quarantine counts
- rule status table (PASS/FAIL)
- sample quarantined rows
- summary statistics (clean dataset)

---

## Dtype Policy (off/warn/error)

Contracts can specify `dtype` per columns (string/int/float/bool/datetime).

Because CSV inputs commonly load everything as strings, dtype validation is off by default.

### Dtype validation modes

- `--dtype-mode off` (default) Ignore dtype compatibility.
- `--dtype-mode warn` Record dtype mismatches in reports but do not fail validation.
- `--dtype-mode error` Fail validation if any dtype mismatch exists (quarantine-all with schema_dtypes).

### Optional coercion

- `--coerce-dtypes` Attempts best-effort casting/parsing (for example, parsing ISO timestamp strings into datetimes).

**Example (warn mode):**

```bash
themis validate \
  --contract contracts/examples/fct_observations.yml \
  --input examples/data/fct_observations.csv \
  --out out_warn/ \
  --dtype-mode warn
```

**Example (error mode and coercion):**

```bash
themis validate \
  --contract contracts/examples/fct_observations.yml \
  --input examples/data/fct_observations.csv \
  --out out_dtype_gate/ \
  --dtype-mode error \
  --coerce-dtypes
```

---

## DuckDB Input Support

DuckDB query results can be validated with Themis using a URI input:

```bash
themis validate \
  --contract contracts/examples/fct_observations.yml \
  --input "duckdb:///examples/data/themis_demo.db?query=select%20*%20from%20fct_observations" \
  --out out_duck/
```

**Recommended install for DuckDB support:**

```bash
pip install -e ".[duckdb]"
```

---

## Run Tests

```bash
pytest -q
```

---

## GitHub Actions Quality Gate

Themis integrates in CI because it returns meaningful exit codes.

A quality gate can run on PRs and fail if ERROR-level violations occur, while uploading reports and quarantined outputs as build artifacts.

See: `.github/workflows/themis-quality-gate.yml`

---

## Potential Extensions

- Referential integrity checks
- Drift checks
- Great Expectations adapter
- Data contract generation improvements (type inference and safer ranges)

---
