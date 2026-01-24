import polars as pl

def df_from_rows(columns, rows):
    return pl.DataFrame({c: [r[i] for r in rows] for i, c in enumerate(columns)})
