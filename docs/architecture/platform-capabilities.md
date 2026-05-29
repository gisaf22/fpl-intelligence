# Platform Capabilities

**Status:** ACTIVE — permanent reference  
**Last revised:** 2026-05-28  
**Superseded by:** ADR required to change any entry

This document defines the eight platform capabilities that every system component must be
designed against. It is the standard, not a checklist. Every design doc must include a
capabilities table that addresses each capability before any code is written.

To change a definition or add a capability, raise an ADR.

---

## The eight capabilities

### 1. Determinism

**What it means:** Given the same inputs, the system always produces the same outputs —
regardless of when it runs, how many times it runs, or who runs it.

**Satisfied when:**
- Output is a pure function of inputs
- No dependency on wall-clock time, random seeds, or external mutable state in the
  computation path
- Source data is pinned (e.g. by hash) so re-runs against the same source produce
  identical output

**Violated when:**
- Output depends on row ordering that is not explicitly sorted
- Rolling windows or aggregations include the current row when they should be lagged
- A build produces different results on two machines or at two times from the same input

---

### 2. Observability

**What it means:** You can understand what the system did and how it performed from its
external outputs, without re-running it or reading its source code.

Sub-pillars for an analytical pipeline:
- **Logs** — what did each layer do, in what order, with what row counts
- **Metrics** — how long did each layer take, how many rows were produced
- **Status** — did each layer pass or fail validation, and if it failed, why

**Satisfied when:**
- Every pipeline run writes a structured manifest with per-layer status, row counts,
  timing, and validation results
- A failure produces an actionable error message that identifies the layer, the check
  that failed, and the first violating rows
- You can answer "when did we last build, did anything fail, what was the GW range?"
  without running any code

**Violated when:**
- Pipeline output is only visible by re-running the pipeline
- A validation failure raises a bare `ValueError` with no layer context
- There is no record of what source data a given output was built from

---

### 3. Contracts

**What it means:** The boundary between every two layers is defined by an explicit,
machine-enforced schema. No layer may produce output that violates its declared contract.
No downstream layer may consume a column that is not declared in that contract.

**Satisfied when:**
- Layer output schema is defined in code (Pandera `DataFrameSchema` at analytical layer
  boundaries; dataclass or typed dict for configuration objects)
- `strict=True` (or equivalent) means undeclared columns are rejected at the boundary
- The contract is the single source of truth — not a comment, not a Markdown doc, not
  an implicit assumption

**Violated when:**
- A column is added to a layer's output without updating the declared schema
- A downstream consumer accesses a column that is not part of the upstream contract
- The contract exists only as a comment or a frozen set with no enforcement

---

### 4. Lineage

**What it means:** For any output, you can trace it back to the source data it was
derived from. For any governance decision (e.g. a signal approval), you can identify
which study produced it and on what data.

**Satisfied when:**
- Every pipeline run records the source database hash
- Every governed column records the gate decision that approved it
- Every study result records the GW range and cutoff it was computed against

**Violated when:**
- An output exists with no record of what source data it was built from
- A governed column exists in the schema with no approval record
- A study finding cannot be linked to a specific run or dataset version

---

### 5. Idempotency

**What it means:** Running the same operation twice produces the same result and does
not corrupt state. It is always safe to re-run.

**Satisfied when:**
- Re-running a build against the same source data produces identical output
- Re-running does not append duplicate rows, double-count values, or leave partial state
- A failed run does not leave the system in a worse state than before it ran

**Violated when:**
- A second run appends to rather than overwrites output
- A failed mid-run leaves partial output that is silently consumed by the next layer
- Cache invalidation is based on mutable state (e.g. file modification time) rather
  than content hash

---

### 6. Testability

**What it means:** Every layer and every contract can be verified in isolation. Tests
do not depend on the full pipeline being runnable.

**Satisfied when:**
- Each layer function accepts its inputs as arguments and returns its outputs — no
  global state, no file I/O inside the transform logic
- A layer can be tested by constructing a minimal valid input DataFrame and asserting
  on the output
- No nested `def` or nested `class` — every symbol is independently importable and
  testable
- Validation modules accept layer-specific constants as parameters rather than
  importing from the layer they validate (V-3 contract)

**Violated when:**
- A layer reads from disk or a database inside its transform logic
- Testing one layer requires constructing the full pipeline
- A validation function imports from the layer it validates, creating a circular
  dependency

---

### 7. Operability

**What it means:** The system is easy to run, restart, debug, and hand to someone else.
A new engineer can run the full pipeline from a clean checkout without reading source code.

**Satisfied when:**
- There is a single documented entry point: `python -m dal.pipeline build`
- Error messages name the layer, the check, and the first violating rows — not a bare
  exception with a line number
- The pipeline fails fast: if a layer fails validation, subsequent layers do not run
- Default configuration works without environment variables (path defaults are sensible)

**Violated when:**
- Running the pipeline requires knowledge not in the README or CONTEXT.md
- An error message requires reading source code to interpret
- A mid-pipeline failure is swallowed and the next layer runs on corrupt input

---

### 8. Evolvability

**What it means:** The system can change — new columns, new layers, new signals —
without silently breaking existing consumers or existing outputs.

**Satisfied when:**
- Schema changes are versioned or gated (adding a column requires updating the schema
  and the approval registry)
- Downstream consumer alignment is enforced by tests (test_downstream_governance.py,
  test_runtime_consumer_alignment.py)
- A breaking change to a layer contract is detectable before deployment, not after

**Violated when:**
- A new column is added to a layer output without updating the schema
- A downstream consumer silently ignores a removed column rather than failing loudly
- There is no way to know whether a consumer is reading a stale schema version

---

## Capability status symbols

Use these in the capabilities table of every design document:

| Symbol | Meaning |
|---|---|
| ✓ | Fully addressed by this design |
| ~ | Partially addressed or consciously deferred — must include a one-line reason |
| ✗ | Known gap — must include a one-line explanation and a resolution path |
| n/a | Not applicable — must include a one-line justification |

A blank cell is never acceptable.

---

## Design doc template — capabilities table

Every design document must include this table, completed, before the changes section.

```markdown
## Capabilities

| Capability   | Status | Notes |
|---|---|---|
| Determinism  | | |
| Observability| | |
| Contracts    | | |
| Lineage      | | |
| Idempotency  | | |
| Testability  | | |
| Operability  | | |
| Evolvability | | |
```
