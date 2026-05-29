# System Purpose

## Mission

fpl-intelligence is an evidence-based analytical system. Its purpose is to determine whether
FPL-related data can meaningfully improve FPL decision-making — and to characterise which
signals, under what conditions, and with what reliability.

The 2025–26 season is the development season. No live decisions are made from system outputs.
The goal is to validate the methodology so that a predictive layer can be built on confirmed
evidence in 2026–27.

## Architectural intent

The system separates three concerns that must remain independent:

1. **Trusted data.** A validated, deterministic, causally-safe data layer (DAL) that all
   analytical work consumes. No analytical decision belongs in this layer.
2. **Analytical investigation.** Research work that characterises signals against the system
   question. No operational output belongs here.
3. **Intelligence outputs.** Scored, synthesised signals consumed for decision support. No
   ad hoc signal logic belongs here.

Keeping these concerns separate prevents analytical assumptions from polluting the data
contract, and prevents operational pressure from shortcutting research rigour.

For the full conceptual model — including the Control Plane (registry and scoring configuration), Execution Plane (DAL + intelligence), and the partially-implemented Measurement Plane — see [docs/architecture/system-model.md](architecture/system-model.md).

## Trusted data assumptions

All downstream analytics operate on a set of guarantees provided by the DAL:

- **Completeness.** Every active player appears in every gameweek (1–38), including BGW
  rows where no fixture occurred.
- **Determinism.** Identical database state produces identical output, byte-for-byte.
- **Temporal causality.** No column in the spine contains data from a future gameweek
  relative to its row. The state layer enforces lag-1 minimum for all derived features.
- **Grain integrity.** The gameweek-grain spine (`player_id`, `gw`) is unique and validated
  before any downstream layer consumes it.
- **Null semantics.** NULL means context does not exist; zero means an observed outcome of
  zero. These are never interchangeable.

These guarantees are contractual. Any DAL code change must preserve them. Code contracts are in `dal/fct/fct_contracts.py` and `dal/validation/`; rationale is in [docs/adr/012-dal-design-rationale.md](adr/012-dal-design-rationale.md).

## Research versus intelligence

**Research** asks: *Does this signal hold up?* It is observational, comparative, and governed
by methodology. Research work lives in `studies/`. It produces characterised signals with
lifecycle status — not decisions.

**Intelligence** asks: *What should I do this gameweek?* It is operational, scored, and
actionable. Intelligence work lives in `intelligence/`. It consumes only signals
that have reached `operationalized` status in the registry.

Research findings do not automatically become intelligence inputs. Promotion through the
signal lifecycle is the gate. See [docs/research-lifecycle.md](research-lifecycle.md).

## Research scope

**In-scope investigation types** — each must be operationally motivated (connected to a named
intelligence output) before a study begins:

- Rolling horizon comparisons — does a 3-GW window outperform a 5-GW or 8-GW window for a specific signal and position?
- Positional signal stability — does a signal's rank correlation remain stable across GW windows?
- Fixture-context usefulness — does fixture difficulty interact with form signals for a specific decision type?
- Minutes reliability characterisation — how stable is playing time across positions and rolling windows?
- Momentum persistence — does form improvement (roll3 > roll5) predict near-term returns better than level form?
- Feature lift over baselines — does a rolling feature outperform a single-game lag signal?
- Horizon sensitivity — how does signal usefulness change as the lookahead window grows from 1 to 5 GWs?

**Explicitly excluded:**

- Causal inference — the system measures association, not cause
- Betting system design — not the domain
- Universal player prediction — out of scope
- Market simulation — FPL price movement and ownership effects
- Transfer market optimisation — constrained squad selection is a separate problem
- Reinforcement learning — no sequential decision modeling
- Probabilistic game simulation — match outcome modeling
- Cross-season signal generalisation — single-season scope for 2025-26
- Opponent defensive modeling — not supported by current spine grain

**Study justification gate** — every study must clear all three before starting:
1. Which intelligence output does this study inform? (`captain.py`, `transfers.py`, `value.py`, `availability.py`, `fixtures.py`)
2. What concrete FPL decision becomes better or worse based on the outcome?
3. Does a prior study already answer this question sufficiently?

A study that fails any gate is rejected, not deferred.

## Operational goals

- Produce a governed signal registry that characterises which FPL signals reliably associate
  with returns, with what correlation strength, in what context.
- Validate whether confirmed signals combine to outperform individual signals (SYNTH-01).
- Support GW-level decision making for transfers, captaincy, and chip selection — grounded
  in characterised evidence.
- Produce a weekly signal intelligence report as the primary operational output.

## Non-goals

- The system is not a pure ML platform. ML experiments are downstream consumers of validated
  signals, not the system's foundation.
- The system is not a heuristic recommendation engine. Signals must pass methodological
  validation before informing decisions.
- The system is not a dashboard or reporting project. Reports are an output, not the purpose.
- The system does not predict FPL points. It characterises signals that associate with FPL
  returns and synthesises them into decision-relevant scores.

## Downstream ML position

ML experiments (`studies/experiments/`) sit at the downstream end of the research pipeline.
They consume validated, synthesised signals — they do not define them. This ordering is
deliberate: ML on unvalidated signals produces results that cannot be diagnosed or improved.

Experiments are a consumer of the research pipeline, not its driver. Architecture decisions
in the DAL and signals layers are not made to accommodate ML requirements.
