# Fixture layer — design and intent

**Status:** intent doc for the informative `fixture/` layer
**Produced:** 2026-06-19 (descriptive-layer redesign)
**Class:** read-only informative artifact (no gate decisions, no PROCEED/STOP verdict)

---

## 1. Purpose and where we sit on the analytics maturity model

`fixture/` characterises how **fixture context** — double vs single gameweek,
fixture difficulty, and home vs away — changes the target picture (`total_points`).
It is the layer the `composition/`, `temporal/`, and `exposure/` notebooks
**deferred to**: those pooled fixture contexts and merely *flagged* the
fixture-doubling / venue confounds; here each is examined head-on.

On **Gartner's analytics maturity model** the layer sits in the **Descriptive**
tier (*what happened?*) — it describes how scoring differs across fixture
contexts. It is **cross-sectional** and season-pooled; it does not explain *why*
(Diagnostic), forecast (Predictive), or recommend (Prescriptive). The target
throughout is `total_points`.

## 2. Notebooks

| Notebook | Question | DGW handling |
|---|---|---|
| `fixture_doubling.ipynb` | Do players score more in a double gameweek — and is it just mechanical doubling or genuine per-fixture lift? | **DGW is the object of study** — SGW vs DGW cohorts |
| `fixture_difficulty.ipynb` | Do players score more against easy fixtures than hard ones, and by how much? | pools SGW + DGW (flags mild DGW inflation; `fdr_avg` is the axis) |
| `home_advantage.ipynb` | How much is home advantage worth, and does it show up as fewer blanks or more returns? | **SGW only** (`was_home` is ambiguous for DGW) |

## 3. Directive questions

**`fixture_doubling.ipynb`**
- Determine how much more players score in a DGW, and whether a DGW is worth
  roughly twice a single gameweek (pure doubling), more (genuine lift), or less
  (fatigue/rotation).
- Establish whether the effect differs by position.
- *(Thin-DGW caveat: DGW player-gameweeks are rare (~1.5% of featured rows);
  every DGW statistic is small-n and the per-position n is stated inline.)*

**`fixture_difficulty.ipynb`**
- Determine whether scoring rises against easier fixtures (lower `fdr_avg`) and
  how large the swing is.
- Establish whether the effect differs by position and whether easy-fixture
  scoring shows up as fewer blanks, more returns, or both.

**`home_advantage.ipynb`**
- Determine how much home advantage is worth in points, by position.
- Establish whether the home edge shows up as fewer blanks, more returns, or
  both.

## 4. Shared method

- **GW range:** whole completed season, `GW 1 .. data_cutoff_gw` (dynamic). No
  early-GW lower bound — the GW-6 cut in the older EDA-1 record was a
  *predictive-evaluation* device, not relevant to descriptive characterisation.
- **Population:** `minutes > 0` participation (the player featured), not a
  performance gate. `minutes` is NULL for BGW (no fixture) rows, so the
  participation filter already excludes them. The 60-minute performance boundary
  is deferred to the `exposure/` layer.
- **Fixture-context axis** (per notebook): `fixture_context` (SGW / DGW),
  binned `fdr_avg` difficulty tiers, and `was_home` venue.
- **DGW handling is per-notebook** (table in §2): `fixture_doubling` studies it
  directly; `fixture_difficulty` pools and flags it; `home_advantage` excludes it
  because a DGW row carries a single ambiguous `was_home` flag for two fixtures.
- **FDR meaning:** `fdr_avg` is the gameweek's average fixture difficulty rating
  (range 1.0–5.0; 1 = easiest, 5 = hardest); a DGW row averages the two
  fixtures' ratings, which is why half-step values appear. (FDR = Fixture
  Difficulty Rating, **not** False Discovery Rate.)

## 5. Deferred

Per-fixture **normalisation** of additive signals (turning a DGW total into a
per-fixture rate) and any **minutes-adjusted** or significance-tested reads are
Diagnostic-tier treatments, not built here. This layer describes the fixture
contexts as they are.
