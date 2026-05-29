# Platform Maturity & Maintainability Assessment Rubric

**Version:** 1.0  
**Owner:** Platform Analytics Engineering  
**Scope:** Governed analytics intelligence platforms  
**Intended Use:** Repeated periodic assessment — not a one-time audit

---

## Purpose

This rubric evaluates whether an analytics platform behaves like a mature, production-grade system with strong operational discipline and low cognitive overhead. It is not a general software engineering checklist. It assumes the project already has layer boundaries, governance metadata, test coverage, and runtime contracts. The question is whether those structures are working — and whether the system is readable, maintainable, and evolvable without requiring historical knowledge to operate.

---

## How to Use

1. For each category, score 1–5 using the scoring guidance.
2. Record evidence sources.
3. Flag critical failures (score ≤ 2 in any CRITICAL category).
4. Compute weighted aggregate score using the scoring methodology section.
5. Map the aggregate to a Platform Maturity Level.
6. Identify the top 3 improvement actions.

---

## Rubric Categories

---

### 1. Architecture & Layer Integrity

**Priority:** CRITICAL

**Why It Matters**

Layer violations are the primary source of long-term platform degradation. When ingestion logic leaks into scoring, or analytical research concepts appear in runtime modules, the system becomes progressively harder to operate. Enforced boundaries allow teams to reason about one layer at a time and change layers independently.

**Observable Indicators**

- Distinct, named layers with documented responsibilities (ingestion, DAL, state, registry, intelligence, outputs)
- No cross-layer imports that bypass the defined dependency direction
- Layer contracts are enforced mechanically (tests, imports, CI checks) — not just by convention
- Architecture documentation matches actual import structure
- New modules land in the correct layer without negotiation

**Anti-Patterns / Failure Modes**

- Intelligence/runtime modules importing from studies or EDA
- State layer calling scoring functions
- Shared utility modules that accumulate cross-layer logic over time
- Architecture diagrams that describe intent rather than reality
- Undocumented "shortcut" imports justified by deadline pressure

**Scoring Guidance**

| Score | Description |
|-------|-------------|
| 5 | All layers are bounded, mechanically enforced, and match documentation. Violations are impossible without a test failure. |
| 4 | Layers are well-defined and mostly enforced. One or two minor boundary tensions exist but are documented. |
| 3 | Layers are named and mostly respected, but enforcement is convention-only. Cross-layer leakage exists but is limited. |
| 2 | Layer names exist but imports frequently cross boundaries. Documentation doesn't reflect reality. |
| 1 | No effective layer separation. Logic is distributed across modules without clear ownership. |

**Evidence Sources**

- Import graph analysis
- Architecture ADRs vs. actual module structure
- Test coverage for layer boundary invariants
- `dal/`, `intelligence/`, `signals/`, `studies/` directory structure

---

### 2. Contracts & Schemas

**Priority:** CRITICAL

**Why It Matters**

Contracts define what each layer guarantees to the next. Without explicit, enforced contracts, every interface is implicitly negotiated at the call site — which means every change risks silent downstream breakage. Contracts are the foundation of reliable evolution.

**Observable Indicators**

- Column contracts, schema contracts, or type contracts are written down explicitly (not inferred from usage)
- Contracts are enforced at runtime or test time — not assumed
- Contract violations surface as clear, actionable errors
- Contract changes require intentional updates to contract definitions
- Nullability, optionality, and cardinality are specified per field

**Anti-Patterns / Failure Modes**

- Schema inferred from the shape of upstream data rather than a declared contract
- Contracts described only in comments with no enforcement
- Downstream code silently handling upstream contract violations (e.g., `.fillna(0)` without a documented reason)
- Column sets that drift between environments
- Contracts that exist in documentation but are never tested

**Scoring Guidance**

| Score | Description |
|-------|-------------|
| 5 | All inter-layer contracts are explicit, versioned, and mechanically enforced. Violations fail fast with clear messages. |
| 4 | Most contracts are explicit and tested. A few low-risk interfaces are convention-only. |
| 3 | Contracts exist for the primary data path but are incomplete for edge cases. Some enforcement gaps. |
| 2 | Contracts are documented but largely unenforced. Runtime violations are possible and discovered late. |
| 1 | No formal contracts. Interfaces are implicit. Changes routinely cause unexpected downstream failures. |

**Evidence Sources**

- `dal/curated/contracts.py`, `dal/state/contracts.py`
- Schema validation modules
- Test files asserting column presence, types, cardinality
- Error messages on contract violation

---

### 3. Runtime Simplicity

**Priority:** CRITICAL

**Why It Matters**

Runtime systems must be operable without reading source code. If understanding why a score was produced requires tracing through multiple abstraction layers, configuration files, and dynamic dispatch chains, the system is fragile under operational pressure. Simplicity is not a lack of sophistication — it is sophistication applied correctly.

**Observable Indicators**

- Scoring path is traceable without a debugger
- Configuration drives behavior; logic does not encode operational parameters
- A new engineer can answer "why did player X get score Y?" within minutes
- Runtime state is deterministic given the same inputs
- No hidden global state or environment-dependent behavior

**Anti-Patterns / Failure Modes**

- Magic numbers embedded in scoring logic without explanation
- Dynamic dispatch that makes the execution path non-obvious
- Runtime behavior that differs between environments without explicit configuration
- Excessive abstraction that obscures what the system actually does
- Analytical methodology leaking into runtime (e.g., EDA-style logic inside the scorer)

**Scoring Guidance**

| Score | Description |
|-------|-------------|
| 5 | Execution path is fully traceable from input to output. Behavior is determined by explicit configuration. No hidden state. |
| 4 | Execution path is clear. One or two abstraction layers add indirection but have clear, documented purposes. |
| 3 | Core path is understandable but some behaviors are non-obvious without reading implementation details. |
| 2 | Significant abstraction overhead. Tracing behavior requires understanding multiple dispatch mechanisms. |
| 1 | Runtime behavior is opaque. Understanding output requires deep implementation knowledge. |

**Evidence Sources**

- `intelligence/_base.py`, scoring engine entry points
- Configuration files vs. hardcoded parameters
- Signal weight registry
- Provenance output for a representative player/gameweek

---

### 4. Naming & Vocabulary

**Priority:** IMPORTANT

**Why It Matters**

Names are the primary interface between the code and the engineer reading it. Inconsistent or domain-leaking names force engineers to maintain a mental translation layer. A shared, precise vocabulary reduces cognitive overhead across all layers and makes onboarding faster.

**Observable Indicators**

- Module, function, and variable names are consistent with the domain vocabulary
- Names describe what something is or does — not how it was built or what phase it came from
- Layer-appropriate vocabulary: DAL uses data terms, intelligence uses decision terms, registry uses control-plane terms
- No abbreviations without glossary backing
- Names don't encode implementation history (e.g., `_v2`, `_new`, `_fixed`)

**Anti-Patterns / Failure Modes**

- Names that reference the research/analytical process rather than the operational concept (e.g., `study_output`, `eda_result`, `wave3_column`)
- Inconsistent naming across layers for the same concept (e.g., `player_id` vs. `element` vs. `fpl_id`)
- Functions named after their implementation rather than their contract (e.g., `apply_rolling_average` vs. `compute_form_signal`)
- Temporal naming that embeds project history (e.g., `legacy_scorer`, `old_registry`)
- Abbreviations that require insider knowledge

**Scoring Guidance**

| Score | Description |
|-------|-------------|
| 5 | All names are consistent, precise, and domain-appropriate. A glossary or vocabulary document backs the terminology. |
| 4 | Names are mostly consistent. A few deviations exist but don't cause confusion. |
| 3 | Core layer names are consistent but some modules or variables drift from the vocabulary. |
| 2 | Noticeable naming inconsistency across layers. Multiple synonyms for the same concept. |
| 1 | Names are arbitrary or historical. Reading names doesn't help understand intent. |

**Evidence Sources**

- Module and function names across `dal/`, `intelligence/`, `signals/`, `studies/`
- Column names across DAL and state layer outputs
- SIGNAL_REGISTRY key names
- Test function names

---

### 5. Docstrings & Comments

**Priority:** IMPORTANT

**Why It Matters**

Comments and docstrings have one job: reduce the time it takes to understand non-obvious code. A comment that restates what the code does adds noise. A comment that explains why a constraint exists, why a threshold was chosen, or what contract is being enforced adds real value. Over-documented code is as harmful as under-documented code — it trains engineers to ignore documentation.

**Observable Indicators**

- Module-level docstrings describe the layer's responsibility and contracts — not its history
- Function docstrings focus on: what it returns, what preconditions it assumes, what errors it raises
- Inline comments explain non-obvious decisions: why a threshold, why a null tolerance, why an ordering constraint
- No comments that describe process history ("added in wave 3"), authorship, or phased delivery
- No commented-out code blocks in production modules

**Anti-Patterns / Failure Modes**

- Comments that narrate the code rather than explain it (`# loop through players`)
- Process-history commentary (`# this was refactored as part of Phase 2`)
- Docstrings that duplicate the function signature with no added information
- TODO comments that have been present for more than one review cycle
- Long module-level docstrings that describe what the module went through rather than what it does
- Absence of any comment on non-obvious constants, tolerances, or thresholds

**Scoring Guidance**

| Score | Description |
|-------|-------------|
| 5 | All docstrings describe contracts, not history. Inline comments explain only non-obvious decisions. No process commentary. Signal-to-noise ratio is high. |
| 4 | Most documentation is operational and relevant. A few verbose or historical comments exist but don't dominate. |
| 3 | Mix of useful and noisy documentation. Some process commentary present. Non-obvious logic is sometimes unexplained. |
| 2 | Documentation is largely decorative or historical. Key constraints are undocumented. Process commentary is common. |
| 1 | Documentation actively misleads or is absent where critical. Commented-out code. History in docstrings. |

**Evidence Sources**

- `intelligence/_base.py`, `signals/lifecycle/lifecycle.py`, `dal/state/player_gameweek_state.py`
- Contract files and their accompanying docstrings
- Any module with threshold constants or null tolerance definitions
- Comments on scoring weights and signal definitions

**Good vs. Bad Examples**

```python
# BAD — narrates the code
# Loop through each player and compute score
for player in players:
    score = compute(player)

# BAD — process history
# Added in Wave 3 to fix the V-3 decoupling issue discovered during DAL stabilization

# BAD — restates signature
def get_player_score(player_id: int) -> float:
    """Gets the player score for a given player id."""

# GOOD — explains the constraint
# Minimum 60 minutes required: FPL awards the appearance bonus only on full participation.
APPEARANCE_THRESHOLD_MINUTES = 60

# GOOD — explains the contract
def promote_signal(key: str, payload: dict) -> None:
    """
    Registers a signal into the live registry.
    Precondition: payload must pass lifecycle gate validation.
    Raises: LifecycleGateError if signal is not in ACTIVE state.
    """
```

---

### 6. Test Quality & Enforcement

**Priority:** CRITICAL

**Why It Matters**

Tests that protect implementation details create refactoring friction without safety. Tests that protect architectural invariants and behavioral contracts catch real failures. The distinction is critical: a high test count with low invariant coverage is worse than a moderate count with strong invariant coverage, because it creates false confidence and maintenance burden.

**Observable Indicators**

- Tests assert behavioral outcomes and contracts — not internal implementation steps
- Architecture invariant tests (layer boundaries, contract shapes) are in the test suite
- Tests are deterministic and environment-independent
- Failure messages identify what invariant was violated and what the consequence is
- Test names describe what behavior is being protected
- Tests for lifecycle gates, registry state machines, and scoring bounds exist

**Anti-Patterns / Failure Modes**

- Tests that assert a specific internal call was made (mocking implementation details)
- Tests named `test_function_X` that test one line of a function in isolation
- Tests that require external state or specific environment configuration
- High test count that doesn't include any contract, schema, or invariant assertions
- Tests that pass when the logic is broken because they mock the wrong boundary

**Scoring Guidance**

| Score | Description |
|-------|-------------|
| 5 | Tests protect real invariants. Architecture, contract, lifecycle, and behavioral tests all present. Names describe what breaks if the test fails. |
| 4 | Strong invariant coverage. A few tests are implementation-specific but don't dominate. |
| 3 | Mix of invariant and implementation tests. Key contracts are tested. Some test names are unclear. |
| 2 | Tests exist but primarily cover happy paths and implementation details. Architecture invariants are not mechanically protected. |
| 1 | Tests exist but provide no real safety net. Refactoring breaks tests that should pass. Real breakage passes tests. |

**Evidence Sources**

- `tests/test_registry_contract.py`, `tests/test_registry_lifecycle.py`
- `tests/stabilization/`
- `tests/test_curated_state_boundary.py`
- Test failure messages on a forced violation

**Good vs. Bad Examples**

```python
# BAD — tests implementation detail
def test_scorer_calls_compute():
    with patch("intelligence.scorer.compute") as mock:
        run_scorer()
    mock.assert_called_once()

# BAD — vague name, unclear what breaks
def test_player_data():
    df = get_player_data()
    assert df is not None

# GOOD — tests a behavioral contract
def test_promoted_signal_must_be_active():
    """Signals in CANDIDATE state must be rejected by the lifecycle gate."""
    with pytest.raises(LifecycleGateError):
        promote_signal("TEST_SIGNAL", state="CANDIDATE")

# GOOD — tests an architectural invariant
def test_intelligence_does_not_import_studies():
    """Runtime scoring must not depend on analytical study outputs."""
    imports = get_all_imports("intelligence/")
    assert not any("studies" in i for i in imports)
```

---

### 7. Configuration & Control Plane Design

**Priority:** IMPORTANT

**Why It Matters**

Operational parameters embedded in code require code changes to adjust. Configuration-driven systems allow operational changes without touching logic — which reduces risk, enables review without deep code context, and separates concerns cleanly. The control plane (registry, thresholds, lifecycle states) is the management interface for the platform.

**Observable Indicators**

- Scoring weights, thresholds, and signal definitions live in configuration — not in logic
- Registry state machine is explicit and enumerated
- Lifecycle state transitions are enforced, not assumed
- Adding a new signal requires configuration changes, not logic changes
- Control plane changes are reviewable without running the system

**Anti-Patterns / Failure Modes**

- Hardcoded scoring weights inside functions
- Signal state (ACTIVE vs. CANDIDATE) checked with string comparisons scattered across modules
- Threshold values that appear in multiple places without a canonical source
- Configuration files that duplicate each other with minor differences
- No clear separation between what the registry controls and what the scorer hardcodes

**Scoring Guidance**

| Score | Description |
|-------|-------------|
| 5 | All operational parameters are config-driven. Registry is the canonical source. Adding signals requires no logic changes. |
| 4 | Most parameters are config-driven. A few constants are hardcoded with clear documentation. |
| 3 | Core weights and thresholds are configurable. Some operational parameters are still embedded in logic. |
| 2 | Config exists but is incomplete. Many operational decisions are still hardcoded. |
| 1 | Operational parameters are scattered through logic. No clear control plane. |

**Evidence Sources**

- `signals/registry/`, `signals/lifecycle/schema.py`
- `intelligence/weight_registry.py`
- Threshold and weight constants across scoring modules
- SIGNAL_REGISTRY definition files

---

### 8. Repository Usability

**Priority:** IMPORTANT

**Why It Matters**

A repository that requires tribal knowledge to navigate is a liability. Every hour spent figuring out where something lives is an hour not spent improving the platform. Usability means a new engineer can locate the entry point, understand the data flow, run the tests, and make a change — without a walkthrough.

**Observable Indicators**

- A single entry point or clear data flow document exists
- Directory structure maps to the conceptual layer model
- Test commands are documented and produce clear output
- New signal onboarding path is documented
- Architecture documents reflect current reality (not aspirational state)

**Anti-Patterns / Failure Modes**

- Multiple competing entry points with no guidance on which to use
- Directory names that reflect project history rather than functional purpose (`wave3_refactor/`, `temp/`, `old_outputs/`)
- Architecture documentation that was accurate 6 months ago but hasn't been updated
- Tests that require undocumented environment setup
- No clear "start here" for a new contributor

**Scoring Guidance**

| Score | Description |
|-------|-------------|
| 5 | New engineer can navigate, run tests, and understand the data flow within one hour without assistance. |
| 4 | Repository is mostly navigable. One or two areas require asking or reading ADRs. |
| 3 | Core paths are documented. Some areas require code reading to understand purpose. |
| 2 | Navigating the repository requires significant prior context or guidance. |
| 1 | Repository is navigable only with tribal knowledge. Documentation is either absent or misleading. |

**Evidence Sources**

- Root-level documentation and README
- `docs/` directory structure
- Directory naming conventions
- ADR index and currency

---

### 9. Operational Governance

**Priority:** IMPORTANT

**Why It Matters**

Governance without enforcement is ceremony. Governance with enforcement is infrastructure. This category distinguishes between systems where governance exists because it was specified, and systems where governance is mechanically wired into the operational path — where it's impossible to bypass without a system failure.

**Observable Indicators**

- Lifecycle gates are enforced in the runtime execution path — not just documented
- Signal promotion requires passing explicit criteria — not manual approval alone
- Governance metadata is machine-readable and consumed by operational tooling
- Violations produce clear, actionable errors — not warnings
- Governance decisions are traceable to specific signals, thresholds, and reasoning

**Anti-Patterns / Failure Modes**

- Governance documents that describe requirements but have no corresponding enforcement
- Lifecycle state stored as a comment or convention rather than a validated field
- Warnings where errors are appropriate
- Governance metadata that exists in documents but is never read by operational code
- Approval processes that can be bypassed by modifying a non-governed file

**Scoring Guidance**

| Score | Description |
|-------|-------------|
| 5 | Governance is mechanically enforced in the execution path. Bypassing governance requires a test failure. |
| 4 | Primary governance controls are enforced. A few secondary controls are convention-based. |
| 3 | Governance structure is well-designed but some enforcement gaps exist. Violations are possible without detection. |
| 2 | Governance is documented but enforcement is sparse. System can be operated in non-compliant states. |
| 1 | Governance exists only as documentation. No mechanical enforcement. |

**Evidence Sources**

- `signals/lifecycle/lifecycle.py`, `signals/evaluation/governance.py`
- Lifecycle gate tests
- Error messages on lifecycle violation
- Signal traceability matrix

---

### 10. Maintainability & Evolution Safety

**Priority:** CRITICAL

**Why It Matters**

A platform that cannot evolve safely is a platform that will be abandoned or rewritten. Evolution safety means: adding a signal doesn't break existing signals; changing a threshold doesn't require touching scoring logic; onboarding a new gameweek doesn't require understanding the full historical pipeline. Maintainability is the product of all the other categories working together.

**Observable Indicators**

- Adding a new signal requires changes in one place (registry) — not scattered across modules
- Changing a scoring weight doesn't require a logic change
- Removing a deprecated signal produces a clear error rather than silent behavior change
- Tests catch regressions in invariants, not just happy-path behavior
- The system can be understood and modified by an engineer who didn't build it

**Anti-Patterns / Failure Modes**

- Changes to one signal require defensive changes across multiple modules
- Deprecated signals are removed from config but remain referenced in logic (silent failures)
- New gameweek onboarding requires touching pipeline logic rather than configuration
- The system has accumulated workarounds that future engineers cannot safely remove
- Refactoring a module requires understanding the full historical context of why it was structured that way

**Scoring Guidance**

| Score | Description |
|-------|-------------|
| 5 | The system is safely evolvable. Signal additions, threshold changes, and deprecations all have clear, enforced paths. |
| 4 | Most evolution paths are safe and documented. A few areas require care but are well-marked. |
| 3 | Core evolution paths work. Some areas have accumulated complexity that creates friction. |
| 2 | Evolution requires significant knowledge of system history. Refactoring introduces regression risk. |
| 1 | The system is not safely evolvable without full knowledge of its history. Changes are high-risk. |

**Evidence Sources**

- Signal onboarding documentation
- Deprecation handling in registry and scorer
- Test suite coverage on evolution paths (signal addition, removal, threshold change)
- ADRs covering evolution decisions

---

## Scoring Methodology

### Category Weights

| Category | Priority | Weight |
|----------|----------|--------|
| Architecture & Layer Integrity | CRITICAL | 1.5x |
| Contracts & Schemas | CRITICAL | 1.5x |
| Runtime Simplicity | CRITICAL | 1.5x |
| Test Quality & Enforcement | CRITICAL | 1.5x |
| Maintainability & Evolution Safety | CRITICAL | 1.5x |
| Naming & Vocabulary | IMPORTANT | 1.0x |
| Docstrings & Comments | IMPORTANT | 1.0x |
| Configuration & Control Plane | IMPORTANT | 1.0x |
| Repository Usability | IMPORTANT | 1.0x |
| Operational Governance | IMPORTANT | 1.0x |

### Aggregate Calculation

```
Weighted Score = Σ(score × weight) / Σ(weights)
Max weighted score = 5.0
```

Weights: CRITICAL = 1.5, IMPORTANT = 1.0  
Total weight: (5 × 1.5) + (5 × 1.0) = 12.5

### Critical Floor Rule

If any CRITICAL category scores ≤ 2, the overall assessment is **BLOCKED** regardless of aggregate score. A single critical failure represents a fundamental platform problem that overrides scoring in other areas.

---

## Severity Interpretation Guide

| Weighted Score | Interpretation | Action |
|----------------|----------------|--------|
| 4.5 – 5.0 | Platform Mature | Maintain. Review quarterly. |
| 4.0 – 4.4 | Operational | Identify top 2 improvement areas. Review semi-annually. |
| 3.5 – 3.9 | Governed | Structured improvement program. Address CRITICAL gaps first. |
| 3.0 – 3.4 | Structured | Prioritize contract enforcement and layer integrity. |
| 2.0 – 2.9 | Ad Hoc | Foundational work required. Focus on CRITICAL categories only. |
| < 2.0 | At Risk | Platform reliability is compromised. Stop feature work. Stabilize first. |

---

## Repository Audit Process

### Preparation (before scoring)

1. Check out a clean copy of the repository at the revision under review.
2. Run the full test suite. Record pass rate and any failures.
3. Run an import graph analysis to enumerate cross-layer imports.
4. Collect the SIGNAL_REGISTRY state snapshot.
5. Identify the five most recently modified modules in `intelligence/` and `signals/`.

### Scoring Session

Score each category independently. Do not score in document order — score in this sequence to avoid anchoring bias:

1. Runtime Simplicity (ground truth of operational behavior)
2. Architecture & Layer Integrity (structural foundation)
3. Contracts & Schemas (inter-layer reliability)
4. Test Quality & Enforcement (safety net quality)
5. Configuration & Control Plane (operational manageability)
6. Maintainability & Evolution Safety (forward safety)
7. Operational Governance (enforcement quality)
8. Naming & Vocabulary (cognitive overhead)
9. Docstrings & Comments (documentation signal-to-noise)
10. Repository Usability (onboarding experience)

### Output

For each category, record:
- Score (1–5)
- One-sentence justification
- Top anti-pattern observed (if score ≤ 3)
- One specific improvement action (if score ≤ 4)

Compute weighted aggregate. Apply critical floor rule. Map to maturity level.

---

## Recurring Review Cadence

| Review Type | Frequency | Scope | Output |
|-------------|-----------|-------|--------|
| Full Assessment | Semi-annual | All 10 categories | Scored rubric + maturity level + top 3 actions |
| Architecture Spot-Check | After each major refactor | Categories 1, 2, 10 | Pass/fail on CRITICAL invariants |
| Documentation Hygiene | Quarterly | Categories 4, 5, 8 | List of files needing cleanup |
| Governance Audit | After signal lifecycle changes | Categories 7, 9 | Enforcement gap report |

---

## Good vs. Bad Examples

### Comments

```python
# BAD: narrates the code
# Get the player dataframe and filter it
df = get_players().query("position == 'MID'")

# BAD: process history in production code
# NOTE: This was rewritten in Wave 3 after V-3 decoupling revealed the old approach
# was reading from the wrong spine. The fix involved... [50 more words]

# GOOD: explains non-obvious constraint
# FPL awards appearance bonus only for ≥60 minutes. Scores below this threshold
# must be treated as partial-participation regardless of actual contribution.
APPEARANCE_THRESHOLD_MINUTES = 60

# GOOD: explains why a null tolerance exists
# Ownership% is sparse in early gameweeks (weeks 1–2). Null tolerance of 0.05
# reflects expected sparsity, not data quality failure.
OWNERSHIP_NULL_TOLERANCE = 0.05
```

### Docstrings

```python
# BAD: restates the signature
def compute_form_signal(player_id: int, window: int) -> float:
    """Computes the form signal for a player over a window."""

# BAD: describes history
def promote_signal(key: str) -> None:
    """
    Promotes a signal. Originally this function also validated the payload,
    but that was moved to the lifecycle gate in Phase 3.
    """

# GOOD: states preconditions, postconditions, and contract
def promote_signal(key: str, payload: dict) -> None:
    """
    Registers a validated signal into the active registry.

    Precondition: payload must have passed lifecycle gate validation.
    Postcondition: signal is queryable via registry.get(key).
    Raises LifecycleGateError if signal state is not ACTIVE.
    """

# GOOD: module-level docstring describes the layer contract
"""
dal/curated/contracts.py

Defines column-level contracts for curated DAL outputs.
Each contract specifies required columns, nullable fields, and cardinality constraints.
Contracts are enforced at DAL exit — no downstream layer may assume a column
that is not declared here.
"""
```

### Naming

```python
# BAD: implementation name, not domain name
def apply_rolling_window_average(values, n):
    ...

# BAD: research language in runtime
def run_eda_profiling_pass(df):
    ...

# BAD: history in name
def get_player_score_v2_fixed(player_id):
    ...

# GOOD: domain name, describes the contract
def compute_form_signal(player_id: int, window: int) -> float:
    ...

# GOOD: control-plane vocabulary
def advance_lifecycle_state(signal_key: str, target_state: LifecycleState) -> None:
    ...
```

### Tests

```python
# BAD: tests implementation detail
def test_compute_calls_rolling():
    with patch("signals.form.rolling_mean") as mock:
        compute_form_signal(1, 5)
    mock.assert_called_once_with(window=5)

# BAD: vague, tests nothing meaningful
def test_player_score_exists():
    result = get_player_score(1)
    assert result is not None

# GOOD: tests behavioral contract
def test_candidate_signal_rejected_at_runtime():
    """Signals in CANDIDATE state must not be used in live scoring."""
    signal = build_signal(state=LifecycleState.CANDIDATE)
    with pytest.raises(LifecycleGateError):
        scorer.include_signal(signal)

# GOOD: tests architectural invariant
def test_intelligence_has_no_studies_dependency():
    """Runtime intelligence layer must not depend on analytical studies."""
    imports = collect_imports("intelligence/")
    study_imports = [i for i in imports if i.startswith("studies.")]
    assert study_imports == [], f"Layer violation: {study_imports}"
```

---

## Platform Maturity Levels

### Level 1 — Ad Hoc

**Repository characteristics:** Scripts and notebooks accumulated over time. Modules exist but aren't organized by layer or responsibility. Data transformations and scoring logic are interleaved.

**Architecture quality:** No enforced boundaries. Layer concept may exist in name but not in practice. Shared utility files accumulate cross-cutting logic.

**Operational discipline:** Configuration is scattered or absent. Parameters are hardcoded. Adding a new signal requires touching multiple files.

**Testing quality:** Tests exist for some functions but don't protect invariants. Refactoring breaks tests for the wrong reasons. High false-safety rate.

**Readability:** The repository requires reading the git history or asking the original author to understand intent.

**Governance quality:** Governance exists as documentation or intent. No mechanical enforcement. It is possible to operate the system in a non-compliant state.

**Maintainability:** High. Risk of regression on any change. No safe evolution path.

---

### Level 2 — Structured

**Repository characteristics:** Modules are organized into directories that correspond to functional layers. Layer responsibilities are documented. Some cross-layer imports remain.

**Architecture quality:** Layer names exist and are mostly respected. Enforcement is convention-based rather than mechanical. Architecture docs are partially accurate.

**Operational discipline:** Core scoring weights may be in configuration. Some thresholds are still hardcoded. Registry concept exists but may not be the canonical source.

**Testing quality:** Tests cover primary data paths and some contracts. Architecture invariants are not mechanically protected. Test names are functional but not self-describing.

**Readability:** Core paths are understandable. Some modules require context to navigate. Naming is mostly consistent with a few deviations.

**Governance quality:** Governance criteria are documented. Lifecycle states exist. Some enforcement is wired in, most is process-based.

**Maintainability:** Safer than Ad Hoc. Most changes are bounded. Some areas accumulate technical debt without visibility.

---

### Level 3 — Governed

**Repository characteristics:** All layers are named, documented, and mostly enforced. Contract definitions exist. Registry is the primary control plane. ADRs cover major decisions.

**Architecture quality:** Layer boundaries are enforced by tests. Cross-layer imports are detected and rejected. Architecture documentation matches current reality.

**Operational discipline:** All operational parameters are config-driven. Registry drives signal inclusion. Lifecycle states are validated at runtime.

**Testing quality:** Contract tests, architecture invariant tests, and lifecycle gate tests are all present. Tests are deterministic. Failure messages describe the invariant violated.

**Readability:** The repository is navigable by an engineer with domain knowledge but no project history. Names are consistent and domain-appropriate.

**Governance quality:** Primary governance controls are mechanically enforced. Signal promotion requires passing explicit criteria. Violations produce errors, not warnings.

**Maintainability:** Safe for most evolution paths. Adding signals is config-only. Threshold changes are centralized. Some areas still require care.

---

### Level 4 — Operational

**Repository characteristics:** The repository operates like infrastructure. Every layer has a clear owner, contract, and enforcement boundary. The control plane is the primary management interface.

**Architecture quality:** All boundaries are mechanically enforced and tested. Import graph matches architecture documentation exactly. No aspirational documentation.

**Operational discipline:** Runtime behavior is fully determined by configuration. No hardcoded operational parameters. Registry is the single source of truth for signal state.

**Testing quality:** Tests protect the right invariants. Failure messages are operational — they describe what broke and why it matters. Test count is meaningful, not inflated.

**Readability:** A new engineer can understand the data flow, run the tests, and make a targeted change within a day. Documentation is accurate and minimal.

**Governance quality:** Governance is indistinguishable from enforcement. Bypassing governance requires a system failure. Traceability is complete.

**Maintainability:** Signal addition, threshold changes, and deprecations all have documented, enforced paths. Evolution is safe and auditable.

---

### Level 5 — Platform Mature

**Repository characteristics:** The platform manages its own operational state. Engineers interact with the control plane, not with source code, for routine operational changes. The system is self-describing.

**Architecture quality:** Architecture is stable and self-enforcing. New contributors understand the system through the architecture alone — implementation details confirm rather than reveal structure.

**Operational discipline:** The system is fully declarative for operational changes. Runtime behavior is deterministic, traceable, and reproducible. Provenance is complete.

**Testing quality:** Tests are minimal and precisely targeted. Every test protects a real invariant. The test suite is a complete behavioral specification of the platform.

**Readability:** The codebase reads as a coherent document — names, structure, and documentation tell a consistent story without requiring historical knowledge.

**Governance quality:** Governance is the execution path. There is no difference between following governance and running the system correctly.

**Maintainability:** The platform can be extended, evolved, and maintained by engineers who were not involved in building it. Institutional knowledge is encoded in the system, not held by individuals.

---

*This rubric is an internal engineering assessment framework. It is calibrated for governed analytics intelligence platforms — not general software engineering, enterprise systems, or distributed infrastructure. Scoring should be applied by engineers with operational platform experience.*
