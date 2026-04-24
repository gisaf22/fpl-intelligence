# FPL Intelligence

## Data Analytics Flow

- DRC defines schema reality.
- DAL provides raw data access.
- EDA produces observations only.
- Hypothesis registry stores potential explanations.
- Experiments validate hypotheses.
- Signals and features use only validated outputs.

## Layer Boundaries

- EDA notebooks must remain purely observational.
- Hypotheses must be tracked outside notebooks in `analysis/experiments/hypothesis_registry.md`.
- Interpretation and validation belong in `analysis/experiments/`, not in `analysis/notebooks/`.
- SQL belongs only in the DAL.
