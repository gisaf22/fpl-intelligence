# System Implementation Contract

**Status:** FROZEN  
**Companion:** docs/adr/006-layer-architecture.md

> **Lifecycle terminology note:** Section 4 of this document uses the historical lifecycle
> vocabulary CANDIDATE → PROPOSED → REGISTERED → DEPRECATED. This is preserved for historical
> accuracy. The active lifecycle model is:
> `exploratory → investigational → candidate → validated → operationalized`
> See [docs/architecture/research-lifecycle.md](research-lifecycle.md) for the authoritative definition.

---

## 1. Final System Contract

### DAL

**Responsibility:** Deterministic, versioned access to player and fixture data.

| | |
|---|---|
| **Allowed inputs** | Raw FPL API artifacts on disk |
| **Allowed outputs** | DataFrames via `dal.access`; typed contracts via `dal.contracts` |
| **Forbidden** | Imports from `studies`, `signals`, or `intelligence`; analytical logic of any kind |

### Studies

**Responsibility:** Measures statistical properties of observed DAL data; writes result artifacts to disk.

| | |
|---|---|
| **Allowed inputs** | `dal.*`; `studies.kernels.*`; external packages |
| **Allowed outputs** | CSV, JSON, or Parquet files written to `studies/runs/` or `outputs/` |
| **Forbidden** | Imports from `signals.*` or `intelligence.*`; assigning signal IDs; writing to `signals/registry/`; defining signal state |

### Signals

**Responsibility:** Stores, validates, and versions study-derived signal entities.

| | |
|---|---|
| **Allowed inputs** | Study artifact files read by path; `dal.*` schema constants only |
| **Allowed outputs** | `SIGNAL_REGISTRY.md` entries; lifecycle state transitions |
| **Forbidden** | Statistical computation on raw data; imports from `studies.*` or `intelligence.*`; classifying raw observations |

### Intelligence

**Responsibility:** Combines validated signals and current DAL data to produce rankings and decisions.

| | |
|---|---|
| **Allowed inputs** | `signals.lifecycle.*`; `signals.registry.*`; `dal.curated`, `dal.state`, `dal.prepared` |
| **Allowed outputs** | Scores, rankings, reports |
| **Forbidden** | Defining signals; computing analytical metrics; imports from `studies.*`; `dal.staging` access without DAL contract exception |

---

## 2. Final Import Rules

### Allowed

```
studies.*      → dal.*
studies.*      → studies.kernels.*
signals.*      → dal.*              (schema constants only)
signals.*      → signals.*          (internal)
intelligence.* → signals.*
intelligence.* → dal.*
tests.*        → any layer
```

### Forbidden

- `studies.*` → `signals.*`
- `studies.*` → `intelligence.*`
- `signals.*` → `studies.*`
- `signals.*` → `intelligence.*`
- `intelligence.*` → `studies.*`
- `dal.*` → any system layer

---

## 3. Final Artifact Rule

- An artifact is a CSV, JSON, or Parquet file produced by a study.
- It is written to `studies/runs/` or `outputs/`.
- Downstream layers consume it by reading the file from disk by path.
- `from studies.kernels.*` is valid inside `studies/` only. All other `from studies.*` imports are forbidden outside `studies/`.

```python
# Correct
results = pd.read_csv("studies/runs/LENS-FORM_20260501_120000.csv")

# Violation
from studies.lenses.form.analysis import get_form_signal_rho
```

---

## 4. Final Glossary

**study** — A Python module in `studies/` that reads DAL data and writes a result artifact. Has no permanent state and no side effects outside its output file.

**kernel** — A Python module in `studies/kernels/` containing domain-agnostic statistical or mathematical functions. No FPL-specific constants, no governance imports, no string classification outputs.

**signal** — A named, versioned analytical finding in `SIGNAL_REGISTRY.md` with an assigned ID (e.g. `FORM-001`). Exists in the system only after promotion through `signals/lifecycle/`.

**registry** — The storage component of `signals/`. Holds the canonical list of promoted signals. Contains no computation logic.

**lifecycle** — The rules governing signal state transitions (CANDIDATE → PROPOSED → REGISTERED → DEPRECATED), enforced exclusively by `signals/lifecycle/`.

---

## 5. Enforcement Model

**Import boundary:** Configure `import-linter` with one contract per layer matching Section 2. Run on every PR. Any violation fails the build.

**Forbidden import check:**
```bash
grep -rn "from studies\.\(lenses\|eda\|experiments\|synthesis\)" \
  --include="*.py" \
  $(find . -not -path "./studies/*" -not -path "./tests/*")
```
Non-zero match = build failure.

**kernels/ gate:** On any PR touching `studies/kernels/`, reviewer confirms: no governance imports, no FPL-specific constants, no string classification outputs, generic numeric or DataFrame inputs and outputs. One failed item = reject.

---

## Freeze Declaration

This system is frozen. Any modification requires breaking-change justification and versioned architectural review.
