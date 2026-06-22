# findings/records/ — Provenance Requirements

**Status:** ACTIVE  
**Issued:** 2026-06-07

---

## Purpose

`research/findings/records/*.csv` contains EDA output files committed to the repository.
These files have no embedded provenance — they will silently age as the underlying database
is refreshed. This document defines the minimum provenance pattern for all files in this
directory.

---

## Sidecar Pattern

Every EDA notebook run that writes to this directory **must** also write a `_provenance.json`
sidecar recording the run context. The sidecar format is:

```json
{
  "produced_by": "eda_03_joint.ipynb",
  "produced_at": "2026-06-07T14:23:00",
  "db_path": "/Users/<user>/.fpl/fpl.db",
  "db_row_count": 7412,
  "files_written": [
    "eda_03_joint_registry.csv",
    "eda_03_rho_decomposition.csv"
  ]
}
```

### Required fields

| Field | Type | Description |
|-------|------|-------------|
| `produced_by` | string | Notebook or script filename |
| `produced_at` | ISO 8601 string | Execution timestamp |
| `db_path` | string | Path to the database used |
| `db_row_count` | integer | `SELECT COUNT(*) FROM mart` at time of run |
| `files_written` | list[string] | CSV filenames written in this run |

---

## Notebook epilogue

Add the following cell as the final cell in each EDA notebook that writes to this directory:

```python
import json
from pathlib import Path
from datetime import datetime

provenance = {
    "produced_by": "<notebook_name>.ipynb",
    "produced_at": datetime.now().isoformat(timespec="seconds"),
    "db_path": str(db_path),
    "db_row_count": len(mart),
    "files_written": [
        # list filenames written above
    ],
}
Path("research/findings/records/_provenance.json").write_text(
    json.dumps(provenance, indent=2)
)
```

---

## Current state

The files in this directory were produced during the 2025-26 EDA phase. No `_provenance.json`
exists for them. Their provenance is recoverable from git history: `git log --follow` on each
file shows the commit date and the notebook that produced it.

Future EDA runs must emit the sidecar before committing new or updated CSV files to this
directory.

---

## CI enforcement

No CI enforcement is implemented. The sidecar pattern is convention. Enforcement may be
added in a future Phase D if the directory grows large enough to require automated auditing.
