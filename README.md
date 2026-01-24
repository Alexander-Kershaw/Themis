***
# Themis
***
**Engine-agnostic Data Contracts, Quality Gates, and Quarantine**

Themis is designed to be reusable validation framework for enforcing **data contracts** before datasets are allowed to enter **silver/gold** layers. It validates schema and rule constraints, splits data into **clean vs quarantine**, and generates **human-readable reports** for debugging and audit trails.

Themis is designed to be reusable across other projects (warehouses, streaming pipelines, analytics engineering stacks), and I intend to incorporate it in future projects.

---

## Goals

- Define dataset contracts in **YAML**
- Validate incoming data against those contracts
- Produce:
  - **pass/fail** status
  - **detailed validation report**
  - **quarantined rows dataset**
- Minimum supported inputs:
  - **CSV**
  - **Parquet**
- Optional stretch:
  - DuckDB tables / query results

---

## Key Concepts

### Validation Phases
Validation happens in phases, from cheap checks to expensive checks:

1. **Schema validation**
   - Required columns exist
   - Types are compatible 

2. **Row validation**
   - Not-null constraints
   - Ranges / allowed values
   - Regex checks

3. **Table validation**
   - Uniqueness (primary key)
   - Drift checks (potential)
   - Referential integrity (potential)

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
Every validation run creates:

- `reports/<dataset>/<run_id>.json`
- `reports/<dataset>/<run_id>.md`

Reports include:

- Counts: total / clean / quarantined
- Rule results (pass/fail, severity)
- Top failing examples (first N bad rows)
- Basic column summary stats

---

## Contract Format (YAML)

Each dataset has its own contract YAML file, e.g.

```yaml

Minimum fields:

```yaml
dataset_name: fct_observations
primary_key: [station_id, ts]
columns:
  - name: station_id
    dtype: string
    required: true
  - name: ts
    dtype: datetime
    required: true
  - name: t2m_c
    dtype: float
    required: true

rules:
  uniqueness: [station_id, ts]
  not_null: [station_id, ts, t2m_c]

severity:
  uniqueness: error
  not_null: error
```

