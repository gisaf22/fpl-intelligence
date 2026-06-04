# Analytical Architecture

**What this is:** the **noun map** of the platform — the analytical objects, in order, and a
pointer to the one artifact that governs each. It is a navigation layer, not a source of truth.
It defines nothing; it tells you where each thing is defined.

It complements the other three "big picture" maps and never restates them:

| Map | Axis | Owns |
|---|---|---|
| [adlc.md](adlc.md) | verb (lifecycle) | how a question becomes a recommendation: explore → validate → model → serve → monitor |
| [system-model.md](system-model.md) | runtime | what each running component is *for*: Control / Execution / Measurement planes |
| [layer-boundaries.md](layer-boundaries.md) | imports | which module may depend on which: `dal → studies → signals → intelligence` |
| **this doc** | noun (objects) | the names of the analytical objects and where each is governed |

---

## 1. Analytical Object Spine

```
Entity ──► Signal ──► Feature ──► Analysis ──► Finding ──► Decision
```

Knowledge moves left to right: the **Entity** spine fixes the grain every analysis stands on; a
**Signal** says what an input column represents; a **Feature** is a materialised representation of
a signal; an **Analysis** tests a feature against a target; a **Finding** is the durable verdict it
produces; a **Decision** consumes governed findings to recommend an action. Each object is owned by
exactly one artifact, listed below.

---

## 2. Object Layer Reference

| Layer | Description | Grain | Authoritative artifact | Governance mechanism |
|---|---|---|---|---|
| **Entity** | The validated record everything else is keyed to | `(player_id, gw)` | [dal/README.md](../../dal/README.md), [grain.py](../../dal/validation/grain.py) | Code-enforced grain contract |
| **Signal** | What an input column represents in the world | conceptual (per signal) | [signal-ontology.md](../foundations/signal-ontology.md) (+ `signal-ontology.yaml`) | Ontology doc |
| **Feature** | A materialised representation of a signal | `(player_id, gw)` column | [feat_schema.py](../../dal/feat/feat_schema.py) `FEATURE_REGISTRY` for column status; [signal_traceability.yaml](../../signals/characterisation/signal_traceability.yaml) for finding routing; [representation-rules.md](../foundations/representation-rules.md) and [representation-governance.md](../foundations/representation-governance.md) for admissibility rules | Code-enforced Pandera contract + per-family rules |
| **Analysis** | A pre-registered test of a feature against a target | per study | [adlc.md](adlc.md), `research/families/*/LENS_DESIGN.md`, [EVAL_DESIGN.md](../../signals/governance/EVAL_DESIGN.md) | Design-locked before code |
| **Finding** | The durable verdict an analysis produces | `signal@lens:target[#POS]` | [evaluation_metadata.yaml](../../signals/governance/evaluation_metadata.yaml), [signal-promotion-states.md](../signal-promotion-states.md) | Code-enforced governance loader |
| **Decision** | A governed recommendation for an FPL action | per module / `(player_id, gw)` | [intelligence-layer.md](intelligence-layer.md), [weight_registry.yaml](../../signals/governance/weight_registry.yaml) | Governed where `signal_id` resolves; editorial where registry marks `PROVISIONAL-EDITORIAL` and uses `derived_from` |

---

## 3. Where Findings Live

Findings are routed by kind. Use this order; do not choose between artifacts ad hoc:

1. **Lens verdicts** (`signal@lens:target[#POS]`) → [evaluation_metadata.yaml](../../signals/governance/evaluation_metadata.yaml)
2. **Composition decisions** (synthesis weights, position-scoped) → [synth01_decisions.yaml](../../signals/governance/synth01_decisions.yaml)
3. **Narrative verdicts** (one slug per verdict) → [docs/decisions/](../decisions/)
4. **EDA gate decisions** (admissibility, pre-lens only) → [research/findings/](../../research/findings/)

---

## 4. Current Maturity Snapshot

Scale: Missing · Emerging · Defined · Governed · Mature. Justification lives in the assessment, not here.

| Layer | Status |
|---|---|
| Entity | Defined (grain enforced); entity ontology Emerging |
| Signal | Governed |
| Feature | Governed |
| Analysis | Defined |
| Finding | Governed |
| Decision | Emerging |

---

## 5. Boundaries

This document does **not** define any of the following. For each, go to its owner:

| Not defined here | Authoritative document |
|---|---|
| Signals (families, scope, temporal type) | [signal-ontology.md](../foundations/signal-ontology.md) |
| Features (admissible representations, per-signal rules) | [representation-rules.md](../foundations/representation-rules.md), [representation-governance.md](../foundations/representation-governance.md) |
| Governance rules (signal states, registry, thresholds) | [signal-promotion-states.md](../signal-promotion-states.md), [registry-governance.md](../registry-governance.md), [governance/](../governance/) |
| Findings (verdicts, weights, rho) | [evaluation_metadata.yaml](../../signals/governance/evaluation_metadata.yaml) |
| Lifecycle stages | [adlc.md](adlc.md) |
| Runtime architecture | [system-model.md](system-model.md) |
| Module ownership / import rules | [layer-boundaries.md](layer-boundaries.md) |

If this document ever states a rule, threshold, weight, verdict, or definition, that fact is in the
wrong place — move it to the owner above and leave a link.
