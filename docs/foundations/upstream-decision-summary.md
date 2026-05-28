# Upstream Decision Summary
## Ontology → Behavior → Representation

**Produced:** 2026-05-25
**Covers:** Phases 1–3 — all decisions upstream of STATE materialization
**Purpose:** Readable reference explaining every signal's status, which layer drove the decision, and why

---

## The three decision layers

Every representation decision passes through three gates in order. A signal that fails an earlier gate never reaches the later ones.

| Layer | Question | Gate type | Failure label |
|---|---|---|---|
| **1 — Ontology** | Is this transform semantically valid for what this signal IS? | Hard stop — no EDA overrides it | REJECTED-SEMANTIC |
| **2 — Behavior** | Does EDA evidence support applying this transform? | Empirical — based on persistence, sparsity, redundancy, association strength | REJECTED-BEHAVIORAL |
| **3 — Rules** | What is the formal outcome? | Synthesis of layers 1 and 2 | APPROVED / CONDITIONAL |

**Key principle:** A positive correlation in EDA does not override a Layer 1 semantic rejection. And passing Layer 1 does not mean approval — Layer 2 still applies.

---

## Signal families

### Process — `xgi`, `xa`, `xg`, `xgc`

Process signals are model-produced estimates of underlying football quality. Rolling mean is semantically valid (estimate type). The key risk is component redundancy — xa and xg are mathematical components of xgi, so their rolling means share most of xgi's information.

---

**xgi** — expected goals involvement (xg + xa) per gameweek

| Layer | Finding |
|---|---|
| Ontology | Process, estimate, Individual scope. Rolling mean admissible. |
| Behavior | Moderate persistence confirmed (EDA-3, EDA-5). Non-sparse for attacking players. Absorbs xa (G-EDA6-02) and absorbs xg at FWD/MID (G-EDA6-03). Rolling windows improve signal at DEF/MID by smoothing game-to-game noise. At FWD, haul concentration is lost when smoothed. |
| Rules | **APPROVED** roll3 and roll5 at DEF and MID (LENS-FORM FORM-001/002). **CONDITIONAL** at FWD — CI excludes zero but decision relevance fails (Q5-Q1 too small, non-monotonic). |

---

**xa** — expected assists per gameweek

| Layer | Finding |
|---|---|
| Ontology | Process, estimate, Individual scope. Rolling mean admissible. |
| Behavior | xa is a direct component of xgi (xgi = xg + xa). Partial_rho with xgi: MID=0.67, GK=0.99. No independent information where xgi is present. Additionally blocked at DEF and FWD in data (G-EDA2-01). |
| Rules | **REJECTED-BEHAVIORAL** all representations (G-EDA6-02). xa remains in spine as raw FPL data (needed for xgi computation), but no STATE representation is approved. |

---

**xg** — expected goals per gameweek

| Layer | Finding |
|---|---|
| Ontology | Process, estimate, Individual scope. Rolling mean admissible. |
| Behavior | xg is a component of xgi. Partial_rho with xgi: FWD=0.93, MID=0.74. Fully absorbed by xgi at FWD and MID. Also blocked at DEF, GK by data sparsity (G-EDA2-01). |
| Rules | **REJECTED-BEHAVIORAL** all representations (G-EDA6-03). xgi is the better, broader signal. |

---

**xgc** — expected goals conceded (team-scope)

| Layer | Finding |
|---|---|
| Ontology | Process, estimate, **Team scope**. Rolling mean admissible. |
| Behavior | EDA-8B: informative at GKP (rho −0.114, G-EDA8-04) but uninformative at DEF (CI crosses zero, G-EDA8-03). However, Layer 2 redundancy check shows xgc is fully explained by goals_conceded + clean_sheets (partial_rho −0.086 and −0.098 respectively — both below 0.30 threshold, G-EDA8-05). The process estimate adds nothing beyond the observed outcomes. |
| Rules | **REJECTED-BEHAVIORAL** all representations (G-EDA8-05). xgc_roll3 and xgc_roll5 currently in STATE — remove in Phase 5. |

---

### Event — `goals_scored`, `assists`, `clean_sheets`, `goals_conceded`, `saves`, `penalties_saved`

Event signals are discrete per-gameweek occurrences. Rolling mean is semantically valid (count type). The key risk is sparsity — rare events diluted by rolling windows lose their spike structure without gaining analytical stability.

`goals_conceded` is truly team-scope — the same value for all players on the team regardless of minutes. `clean_sheets` is a team event with player-conditioned encoding: FPL awards clean_sheets=1 only to players who played ≥60 minutes. Values differ across teammates by minutes played.

---

**goals_scored**

| Layer | Finding |
|---|---|
| Ontology | Event, count, Individual scope. Rolling mean admissible. |
| Behavior | Sparse and bursty — high raw rho at FWD (0.85) and MID (0.58) is haul-driven. Rolling mean destroys burst structure: goals_scored_roll3 uninformative at all positions (LENS-FORM FORM-003). The smoothed signal produces near-zero averages that no longer identify when hauls occurred. |
| Rules | **CONDITIONAL** raw lag-1 (haul-concentration caveat applies). **REJECTED-BEHAVIORAL** roll3, roll5, roll8 — rolling mean converts a sparse haul signal into a near-zero average (LENS-FORM FORM-003). |

---

**assists**

| Layer | Finding |
|---|---|
| Ontology | Event, count, Individual scope. Rolling mean admissible. |
| Behavior | EDA-3's assists rho (0.49 MID, 0.36 FWD) was **contemporaneous** — same-GW assists vs same-GW points, which is definitionally correlated in FPL. EDA-8D established the first **lag-1 characterisation** (lag-1): rho ≈ 0.04 at MID. None of raw, roll3, or roll5 clears the naive baseline (points_roll3 rho=0.14 at MID). Q5-Q1 gaps near-zero and non-monotonic across all positions and windows. Assists as a process signal is superseded by xgi. |
| Rules | **REJECTED-BEHAVIORAL** all representations (G-EDA8-07/08/09/10). assists_roll3 and assists_roll5 currently in STATE — remove in Phase 5. |

---

**clean_sheets** *(Team scope)*

| Layer | Finding |
|---|---|
| Ontology | Event, count, Team scope. Rolling mean admissible. |
| Behavior | Binary defensive outcome per match. Mild persistence from team defensive quality, but individual match is highly variable. LENS-FIXTURE-GW did not study rolling clean_sheets representations — only context signals were covered. Rolling window behavior not validated. xgc redundancy (G-EDA8-05) confirmed clean_sheets is a surviving defensive outcome signal. |
| Rules | **CONDITIONAL** raw lag-1 and roll3/roll5 — semantically admissible, not yet lens-validated. Team scope annotation required. |

---

**goals_conceded** *(Team scope)*

| Layer | Finding |
|---|---|
| Ontology | Event, count, Team scope. Rolling mean admissible. |
| Behavior | Team-scope count. Moderate_shift at MID between season halves (G-EDA5) adds seasonal drift risk for rolling variants. LENS-FIXTURE-GW did not study rolling goals_conceded. Survives as primary defensive outcome signal (xgc excluded at G-EDA8-05). |
| Rules | **CONDITIONAL** raw lag-1 and roll3/roll5 — semantically admissible, not yet lens-validated. MID seasonal drift risk noted. Team scope annotation required. |

---

**saves**

| Layer | Finding |
|---|---|
| Ontology | Event, count, Individual scope. Rolling mean admissible. Blocked as structural zero at DEF/MID/FWD (G-EDA2-03) — REJECTED-SEMANTIC for outfield. |
| Behavior | EDA-8A: saves GKP lag-1 → next-GW total_points rho = −0.029, CI crosses zero, 0/3 block stability. The near-zero negative rho is consistent with a structural tension: a GK facing many shots is likely on a team under defensive pressure → goals conceded → no clean sheet (the primary GK scoring event). This would suppress any positive association. The mechanism was not directly tested. |
| Rules | **REJECTED-SEMANTIC** all positions for outfield (structural zero). **REJECTED-BEHAVIORAL** all representations at GKP (G-EDA8-01/02). saves_roll3 and saves_roll5 currently in STATE — remove in Phase 5. |

---

**penalties_saved**

| Layer | Finding |
|---|---|
| Ontology | Event, count, Individual scope. Rolling mean admissible in principle. |
| Behavior | EDA-8C sparsity gate: 99.7% zero-rate across 2,512 GKP player-GW records. Only 8 non-zero records total. Only 6 distinct GKPs ever saved a penalty. Rolling mean of near-all-zeros produces a near-constant near-zero column — it doesn't smooth noise, it erases the rare meaningful spike. More extreme than the red_cards exclusion from EDA-2. |
| Rules | **REJECTED-BEHAVIORAL** all representations (G-EDA8-06). Layer 1 ineligible — no study warranted. penalties_saved_roll3 and penalties_saved_roll5 currently in STATE — remove in Phase 5. |

---

### Participation — `minutes`

Participation signals measure playing time. Rolling mean is semantically valid (rate type). Minutes is explicitly blocked as a quality/form signal — it measures availability, not performance level.

---

**minutes**

| Layer | Finding |
|---|---|
| Ontology | Participation, rate, Individual scope. Rolling mean admissible. Blocked as form/quality signal (G-EDA2-02) — availability only. |
| Behavior | High persistence: managers allocate minutes consistently to established starters. LENS-AVAIL confirmed all three windows (roll3, roll5, roll8) informative at MID. roll8 is the strongest availability signal at DEF. GK and FWD uninformative across all windows. |
| Rules | **APPROVED** minutes_roll3 at MID; minutes_roll5 at MID; minutes_roll8 at DEF and MID (LENS-AVAIL AVAIL-001/002/003). **CONDITIONAL** minutes_trend — in STATE output, 30-minute threshold undocumented; requires behavioral justification or removal. |
| Operational note | Current code uses minutes_roll3, minutes_roll5, and minutes_trend as **gate inputs** — binary availability risk classification (HIGH/MEDIUM/STABLE) in `intelligence/availability.py` — not as scored signals contributing to a ranking. minutes_roll8 is produced in STATE but not wired to any gate or scoring logic. The EDA approval (AVAIL-001/002/003) establishes analytical informativeness; it does not determine whether operational use is gating or scoring. That distinction is a Phase 4/7 decision. |

---

### Market — `transfers_in`, `transfers_out`, `ownership_count`

Market signals represent population-level FPL manager behavior, not individual football performance. Rolling mean is inadmissible for this family — it mixes current and stale managerial sentiment across different decision cycles. Point-in-time is the only valid form. All Market columns carry `scope: Population`.

---

**transfers_in**

| Layer | Finding |
|---|---|
| Ontology | Market, count, Population scope. Rolling mean inadmissible (family rule) — REJECTED-BEHAVIORAL by default. |
| Behavior | Reactive to events (injury returns, price rises, fixture runs). Low persistence. Informative at DEF and MID (rho≈0.187-0.190, passes 3/3 blocks). GK and FWD fail decision relevance. |
| Rules | **APPROVED** point-in-time lag-1 at DEF and MID (LENS-MARKET MARKET-001). Rolling mean REJECTED-BEHAVIORAL. |

---

**transfers_out**

| Layer | Finding |
|---|---|
| Ontology | Market, count, Population scope. Rolling mean inadmissible (family rule). |
| Behavior | Not independently studied. transfers_balance (in minus out) studied as MARKET-002 — uninformative at all positions. |
| Rules | **CONDITIONAL** point-in-time — not independently lens-validated; Market family rule applies by analogy. Rolling mean REJECTED-BEHAVIORAL. |

---

**ownership_count**

| Layer | Finding |
|---|---|
| Ontology | Market, **stock**, Population scope. Rolling mean **REJECTED-SEMANTIC** — averaging a level over time has no coherent interpretation. Delta is the admissible derivative. |
| Behavior | Stock signal — cumulative manager count; changes slowly. High persistence. Informative at DEF and MID (rho≈0.156-0.168, passes 3/3 blocks). FWD unstable (1/3 blocks). GK uninformative. |
| Rules | **APPROVED** point-in-time lag-1 at DEF and MID (LENS-MARKET MARKET-003). **REJECTED-BEHAVIORAL** delta — ownership_count delta = transfers_balance by definition; tested as MARKET-002, uninformative at all positions. Rolling mean REJECTED-SEMANTIC (stock type). |

---

### Structural Tier — `purchase_price`

Structural Tier signals are system-computed values encoding player quality tier. In-season prices change with transfer activity — the FPL price algorithm takes transfer demand as input. Distinct from Market signals in that purchase_price is a system output, not a direct count of manager actions. Rolling mean is inadmissible (stock type). Delta is inadmissible — price changes reflect FPL mechanics, not independent football signal.

---

**purchase_price**

| Layer | Finding |
|---|---|
| Ontology | Structural Tier, **stock**, Individual scope. Rolling mean REJECTED-SEMANTIC. Delta inadmissible. |
| Behavior | Slow-changing structural encoding of player quality tier. Informative at DEF and FWD (passes 2/3 GW blocks each). GK and MID fail decision relevance. |
| Rules | **APPROVED** point-in-time lag-1 at DEF and FWD (LENS-MARKET MARKET-004). Rolling mean REJECTED-SEMANTIC. Delta REJECTED-BEHAVIORAL. |

---

### Allocation — `bonus`, `bps`

Allocation signals are FPL system constructs computed from in-match outcomes. Using them as analytical representations of total_points introduces target leakage — bonus is a direct component of total_points, and bps drives bonus allocation. The association is real but analytically circular.

---

**bonus**

| Layer | Finding |
|---|---|
| Ontology | Allocation, count, Individual scope. Rolling mean admissible in principle. |
| Behavior | core_signal at DEF and GK (contemporaneous rho=0.54). High association is circular — bonus is a component of total_points. Using bonus to associate with total_points leaks target information. |
| Rules | **REJECTED-BEHAVIORAL** all representations as analytical representations (G-EDA7-06). If materialized in STATE, must carry `leakage_risk: in_match_allocation`. Must not be consumed by operational scoring. |

---

**bps** — bonus points system index

| Layer | Finding |
|---|---|
| Ontology | Allocation, count, Individual scope. Rolling mean admissible in principle. |
| Behavior | core_signal at GK (contemporaneous rho=0.91). Extreme association because bps directly drives bonus allocation, which is a component of total_points. Analytically circular. |
| Rules | **REJECTED-BEHAVIORAL** all representations as analytical representations (G-EDA7-06). Same leakage annotation requirement as bonus. |

---

### Context — `fdr_avg`, `fdr_max`, `fdr_min`, `was_home`, `fixture_count`

Context signals are fully determined before the match begins. They describe a fixture, not a player's temporal trajectory. **All temporal transforms are inadmissible by ontology regardless of temporal type** — there is no "recent fixture difficulty form" that belongs to the player. Context signals appear in STATE as raw labels only.

All Context columns carry `scope: Match` and `causality: pre-match-determined`.

---

**fdr_avg** — fixture difficulty rating (gameweek average)

| Layer | Finding |
|---|---|
| Ontology | Context, estimate, Match scope. All temporal transforms REJECTED-SEMANTIC (pre-match fixed). |
| Behavior | Negative rho confirmed at all positions (DEF −0.196, MID −0.159) — harder fixtures → fewer points, as expected. But fails decision relevance at all positions: Q5-Q1 gap is negative and non-monotonic. Cannot function as a simple directional rank signal. G-EDA6-01: sole representative of the fdr_* family (fdr_max and fdr_min are perfectly redundant). |
| Rules | **APPROVED** as raw context label. Rolling mean REJECTED-SEMANTIC. Directional rank indicator REJECTED-BEHAVIORAL (LENS-FIXTURE-GW FIXTURE-001). **CONDITIONAL** as binary difficulty moderator (easy/medium/hard tercile) — deferred to SYNTH-01. |

---

**fdr_max** and **fdr_min**

| Layer | Finding |
|---|---|
| Ontology | Context, estimate, Match scope. All temporal transforms REJECTED-SEMANTIC. |
| Behavior | Pairwise rho with fdr_avg = 1.0 at all positions (G-EDA6-01). Perfectly redundant — carry zero independent information. |
| Rules | **REJECTED-SEMANTIC** all representations. Retained in spine as raw DGW structural metadata (fdr_max/min are meaningfully distinct from fdr_avg only in double gameweeks, so they have structural value in the source data). No STATE representation warranted. |

---

**was_home**

| Layer | Finding |
|---|---|
| Ontology | Context, **indicator**, Match scope. All transforms REJECTED-SEMANTIC — no magnitude, no valid arithmetic. |
| Behavior | LENS-FIXTURE-GW confirmed empirically uninformative (rho≈0.044-0.068 at DEF/MID; fails decision relevance). This confirms but does not constitute the exclusion — the exclusion is ontology-derived. |
| Rules | **APPROVED** as raw binary context label (use as moderator/grouping variable). All temporal transforms REJECTED-SEMANTIC. |

---

**fixture_count**

| Layer | Finding |
|---|---|
| Ontology | Context, count, Match scope. All temporal transforms REJECTED-SEMANTIC (pre-match fixed). Additionally blocked at FWD and GK (G-EDA2-01). |
| Behavior | LENS-FIXTURE-GW: rho≈0.098 DEF / 0.083 MID in full DGW-inclusive sample, but CI crosses zero when DGW rows are removed. The entire apparent signal is the fixture multiplier effect (DGW = 2 fixtures), not fixture_count as an independent signal. |
| Rules | **APPROVED** as raw context label (useful for DGW identification). All transforms REJECTED-SEMANTIC. |

---

### Outcome — `total_points`

The analysis target. Using its rolling mean as an analytical representation is circular. The lag-1 raw value serves as the mandatory naive baseline in evaluation comparisons — it is not an operational representation.

---

**total_points**

| Layer | Finding |
|---|---|
| Ontology | Outcome, count, Individual scope. Rolling mean admissible in principle. |
| Behavior | Right-skewed (skew=1.58). Lag-1 raw is the mandatory naive baseline (G-EDA7-02). points_roll3 uninformative or unstable at all positions (LENS-FORM FORM-004). points_roll5 informative at MID only (rho=0.157; LENS-FORM FORM-005) — position-conditional and serves as a comparison baseline, not a feature. |
| Rules | **APPROVED** lag-1 as naive evaluation baseline only — not an operational representation. **CONDITIONAL** roll5 at MID as evaluation baseline only. **REJECTED-BEHAVIORAL** rolling mean as primary analytical representation — circular use of the target variable. |

---

## Consolidated outcome

| Signal | Family | STATE representation | Status | Layer that decided |
|---|---|---|---|---|
| xgi_roll3/5 | Process | In STATE | APPROVED DEF/MID | Layer 2 (EDA confirmed) |
| xa | Process | Not in STATE | REJECTED-BEHAVIORAL | Layer 2 (redundant with xgi) |
| xg | Process | Not in STATE | REJECTED-BEHAVIORAL | Layer 2 (absorbed by xgi) |
| xgc_roll3/5 | Process | In STATE — remove | REJECTED-BEHAVIORAL | Layer 2 (redundant with outcomes) |
| goals_scored raw | Event | In spine | CONDITIONAL | Layer 2 (haul caveat) |
| goals_scored_roll* | Event | In STATE — remove | REJECTED-BEHAVIORAL | Layer 2 (destroys burst) |
| assists_roll* | Event | In STATE — remove | REJECTED-BEHAVIORAL | Layer 2 (fails naive baseline) |
| clean_sheets_roll* | Event | In STATE | CONDITIONAL | Layer 2 (not lens-validated) |
| goals_conceded_roll* | Event | In STATE | CONDITIONAL | Layer 2 (not lens-validated) |
| saves_roll* (outfield) | Event | In STATE — remove | REJECTED-SEMANTIC | Layer 1 (structural zero) |
| saves_roll* (GKP) | Event | In STATE — remove | REJECTED-BEHAVIORAL | Layer 2 (uninformative) |
| penalties_saved_roll* | Event | In STATE — remove | REJECTED-BEHAVIORAL | Layer 2 (structurally sparse) |
| minutes_roll3/5 | Participation | In STATE | APPROVED MID | Layer 2 (EDA confirmed) |
| minutes_roll8 | Participation | In STATE | APPROVED DEF/MID | Layer 2 (EDA confirmed) |
| minutes_trend | Participation | In STATE | CONDITIONAL | Layer 2 (threshold undocumented) |
| transfers_in | Market | In STATE | APPROVED DEF/MID | Layer 2 (EDA confirmed) |
| transfers_out | Market | In STATE | CONDITIONAL | Layer 2 (not lens-validated) |
| ownership_count | Market | In STATE | APPROVED DEF/MID | Layer 2 (EDA confirmed) |
| ownership_count rolling | Market | — | REJECTED-SEMANTIC | Layer 1 (stock type) |
| purchase_price | Structural | In STATE | APPROVED DEF/FWD | Layer 2 (EDA confirmed) |
| purchase_price rolling | Structural | — | REJECTED-SEMANTIC | Layer 1 (stock type) |
| bonus | Allocation | In STATE | REJECTED-BEHAVIORAL | Layer 2 (target leakage) |
| bps | Allocation | In STATE | REJECTED-BEHAVIORAL | Layer 2 (target leakage) |
| fdr_avg | Context | In STATE (raw label) | APPROVED as label | Layer 1 (Context = raw only) |
| fdr_max / fdr_min | Context | Spine only, not STATE | REJECTED-SEMANTIC | Layer 1 + Layer 2 (redundant + Context) |
| was_home | Context | In STATE (raw label) | APPROVED as label | Layer 1 (Context = raw only) |
| fixture_count | Context | In STATE (raw label) | APPROVED as label | Layer 1 (Context = raw only) |
| total_points lag-1 | Outcome | Evaluation baseline | APPROVED as baseline | Layer 2 (naive baseline role) |
| total_points rolling | Outcome | — | REJECTED-BEHAVIORAL | Layer 2 (circular representation) |

---

## Phase 5 cleanup — columns to remove from STATE

These columns are currently produced but have no approved justification:

| Columns | Reason | Gate |
|---|---|---|
| xgc_roll3, xgc_roll5 | Redundant with goals_conceded + clean_sheets | G-EDA8-05 |
| goals_scored_roll3, goals_scored_roll5 | Rolling mean destroys burst structure | LENS-FORM FORM-003 |
| assists_roll3, assists_roll5 | Fails naive baseline at all positions | G-EDA8-07/08/09/10 |
| saves_roll3, saves_roll5 | Uninformative GKP; structural zero outfield | G-EDA8-01/02; G-EDA2-03 |
| penalties_saved_roll3, penalties_saved_roll5 | Structurally sparse (99.7% zero-rate) | G-EDA8-06 |
