"""Hash-level reproducibility artifact for DAL output validation."""

import hashlib

import pandas as pd


def compute_spine_fingerprint(df: pd.DataFrame) -> dict:
    """Return a reproducibility fingerprint for an output spine."""
    sorted_df = df[sorted(df.columns)]
    row_hashes = pd.util.hash_pandas_object(sorted_df, index=True)
    content_hash = hashlib.sha256(row_hashes.values.tobytes()).hexdigest()
    return {
        "sha256": content_hash,
        "n_rows": len(df),
        "n_cols": len(df.columns),
        "columns": list(df.columns),
        "dtypes": {col: str(df[col].dtype) for col in df.columns},
    }
