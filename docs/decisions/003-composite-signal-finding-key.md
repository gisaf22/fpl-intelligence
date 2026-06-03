# ADR-003 — Composite Signal-Finding Key Scheme

**Status:** Accepted  
**Date:** 2026-06-03 (Phase 6 — ID-diet code migration)  
**Applies to:** `signals/governance/evaluation_metadata.yaml`, `signals/governance/synth01_decisions.yaml`, `signals/governance/governance.py`, `signals/governance/schema.py`  
**ADLC source:** [§6 "keep two" — composite signal key](../architecture/adlc.md) + the feasibility caveat

---

## Context

A *signal finding* is the durable unit of governance in this repo: the verdict that a given input
column, tested under a given evaluation lens against a given target, is informative (or not) at a
given position. These findings were keyed by opaque sequential codes — `FORM-006`, `AVAIL-001`,
`G-SYNTH1-09` — carried as `signal_id` in `evaluation_metadata.yaml` and `decision_id` in
`synth01_decisions.yaml`. ADLC §6 ("six namespaces down to two") retires those codes. The naive
replacement — "just use the bare column name as the key" — is **wrong**, and the governance data
proves it.

**The worked counter-example (why the bare column fails).** The column `minutes_roll3` is evaluated
under **two** lenses, with **opposite verdicts**:

| Old code | Column | Lens | Target | Verdict |
|---|---|---|---|---|
| `FORM-006` | `minutes_roll3` | FORM | `total_points` | **REJECTED** at every position (non-monotonic; minutes blocked as a form proxy) |
| `AVAIL-001` | `minutes_roll3` | AVAIL | `played_next_gw` | **approved at MID** (monotonic availability separation, 3/3 blocks) — the synth decision `G-SYNTH1-09` |

Same column, opposite verdicts. A bare-column key (`minutes_roll3`) cannot represent both; it would
collapse a rejection and an approval into one ambiguous row. The column names the *input*; a finding
is `(signal × lens/target × position)`. Today the runtime hides this collision behind a
lifecycle-priority tiebreak in `get_signal_governance(signal, position)` — correct, but *implicit*.
The composite makes the disambiguating axes explicit and the key self-describing.

---

## Decision

Adopt a **composite finding key** as the canonical identifier for every signal finding. The grammar
mirrors the three axes a finding actually has:

```
finding key            =  signal @ lens : target
position-scoped key    =  signal @ lens : target # POSITION
```

- `@` separates the **signal** (input column) from the **lens** (evaluation framing).
- `:` separates the lens from the **target** (the outcome the signal was tested against).
- `#` (when present) scopes the finding to one **position** — used for synth-composition decisions,
  which are inherently position-specific.

**Token normalisation (deterministic, so the key is derivable, not hand-typed):**

- lens token = `lens.lower().replace("-", "_")` → `FORM`→`form`, `AVAIL`→`avail`,
  `MARKET`→`market`, `FIXTURE-GW`→`fixture_gw`.
- target = the `target` field verbatim (`total_points`, `played_next_gw`).
- position = the position label verbatim (`GK`/`DEF`/`MID`/`FWD`).

So a finding's key is a **pure function of its own `signal`, `lens`, and `target` fields** (plus
position for synth decisions). It is not a new free-text field that can drift from the data — a
meta-test asserts `key == derive(signal, lens, target[, position])` for every row.

**Worked examples:**

| Old code | Composite key |
|---|---|
| `FORM-006` | `minutes_roll3@form:total_points` |
| `AVAIL-001` | `minutes_roll3@avail:played_next_gw` |
| `FIXTURE-001` | `fdr_avg@fixture_gw:total_points` |
| `G-SYNTH1-09` | `minutes_roll3@avail:played_next_gw#MID` |
| `G-SYNTH1-07` | `xgi_roll3@form:total_points#MID` |

A synth decision's key is exactly its **parent finding's key plus `#POSITION`**. This makes the
`evaluation_metadata → synth01_decisions` cross-reference self-validating: the AVAIL-001 entry's MID
block references `minutes_roll3@avail:played_next_gw#MID`, which is unambiguously the AVAIL finding at
MID — never the FORM one. A meta-test enforces `synth_decision_key == f"{finding_key}#{position}"`.

**Relation to the existing `signal@position` convention.** Runtime governance-violation messages
already use a loose `signal@position` shorthand (e.g. `purchase_price@GK`). That shorthand is the
*degenerate* form — signal and position only, no lens/target — sufficient for an error string but not
a key (it cannot disambiguate the `minutes_roll3` collision). This ADR formalises the full grammar for
*keys*; violation messages may keep the short form (it is prose, not a lookup).

**Loader semantics.** `governance.py` gains an explicit composite lookup,
`get_signal_governance_by_key(key)`: it parses `signal@lens:target[#POS]`, resolves the finding
*directly* by `(signal, lens, target)` — collision-free, no priority tiebreak — and **raises**
`GovernanceMetadataError` on a missing or malformed key (no silent default). The existing
`get_signal_governance(signal, position)` API is unchanged for the real consumers (the scorer holds
only signal + position, not lens/target); it keeps its lifecycle-priority disambiguation, now
*explained* by the composite rather than hidden. Every `GovernanceMetadata` carries `.key` (the
finding composite), replacing the retired `.signal_id`.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| **Bare column name** (`minutes_roll3`) | Cannot represent the FORM-rejected / AVAIL-approved collision — collapses opposite verdicts into one ambiguous key. The exact failure ADLC §6 calls out. |
| **Keep opaque codes** (`FORM-006`, `AVAIL-001`) | Not self-describing — the reader cannot recover *what was tested* from the key. Sequential codes also imply an ordering that carries no meaning and drift from the data they label. |
| **Keep `signal_id` field name, composite value** | Lower churn, but `signal_id` becomes a misnomer (a key is not an id) and the retired namespace lingers as a field name. Rejected in favour of a clean rename to `key`. |
| **Carry both `key` and `signal_id`** | Leaves `FORM-*` as a live, load-bearing field — violates the Phase 6 done-criterion that the killed namespaces no longer appear as load-bearing keys. |
| **`@POSITION` suffix for synth decisions** | Overloads `@` (already = lens boundary) with a second meaning in one string. `#` gives position its own unambiguous separator. |
| **Separate `position` field only (no position in key)** | A synth decision's identity *is* position-specific; encoding it in the key makes the parent-finding cross-reference self-validating, which a side field does not. |

---

## Capabilities

| Capability   | Status | Notes |
|---|---|---|
| Determinism  | ✓ | The key is a pure function of `(signal, lens, target[, position])` via fixed token normalisation; identical inputs always yield the identical key. |
| Observability| ✓ | The key is self-describing — a reader (or a violation message: `Source: minutes_roll3@avail:played_next_gw`) sees the signal, lens, and target tested, with no code lookup. |
| Contracts    | ✓ | `get_signal_governance_by_key` hard-fails (`GovernanceMetadataError`) on a missing/malformed key — no silent default. A meta-test asserts every materialised key equals its derived form, so the key cannot drift from the row it labels. |
| Lineage      | ✓ | The composite *is* the lineage: it names which lens/target evaluation produced the verdict. The synth `#POSITION` key ties each composition decision to its exact parent finding. |
| Idempotency  | ✓ | Migration is a one-time representation change; re-deriving a key from the same fields is repeatable and side-effect-free. Verdicts, weights, lifecycle, and per-position fields are preserved unchanged. |
| Testability  | ✓ | `get_signal_governance_by_key` takes a string and returns metadata or raises — testable in isolation. Migration tests cover resolves-all, hard-fails-on-missing, derive-consistency, and cross-ref self-validation. |
| Operability  | ~ | Keys are longer than `FORM-006`; mitigated by the self-describing payoff and deterministic derivation (no one hand-types or memorises them). Consumers still call the unchanged `(signal, position)` API. |
| Evolvability | ✓ | A new lens, target, or signal yields a new well-formed key with no scheme change. The existing guard tests (`test_runtime_consumer_alignment`, `test_runtime_metadata_propagation`) hold consumer alignment across the migration. |

---

## Consequences

- `evaluation_metadata.yaml` (16 findings) and `synth01_decisions.yaml` (14 decisions) drop their
  `signal_id` / `decision_id` code fields for a `key` composite. The per-position
  `synth01_decision_id` cross-references become `#POSITION` keys. No verdict, weight, lifecycle
  state, rho, or per-position field changes — only the key representation.
- `GovernanceMetadata.signal_id` is renamed to `.key`; `governance.py`, `signal_selector.py`'s three
  violation messages, and the `signal_id`-value assertions in `test_runtime_metadata_propagation.py`
  follow. `weight_registry.yaml`'s `signal_id:` cross-references to findings are updated to composite
  form for consistency (they are narrative pointers, not loader keys).
- `FORM-*`, `AVAIL-*`, `MARKET-*`, `FIXTURE-*`, and `G-SYNTH1-*` no longer appear as load-bearing
  keys. They may survive in archived docs and historical notebooks (read-only records), and as
  narrative mentions repointed at the decision-slug log per [ADR-004](004-decision-slug-log.md).
- New findings are added by writing the `signal`/`lens`/`target` fields; the key is derived and
  meta-test-checked, so a malformed or drifted key fails CI rather than silently mis-resolving.
