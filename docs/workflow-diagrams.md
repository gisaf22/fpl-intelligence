# Workflow Diagrams — fpl-intelligence

Visual companion to [workflow-map.md](workflow-map.md). That document is the source of
truth; every node and edge here traces to an import, call, or artifact recorded there.
Where the map marks something UNVERIFIED it is drawn dotted and suffixed `?`.

> **Amended 2026-08-16.** Commit `ae90398` deleted `serve/scoring/`, `serve/reporting/`,
> `outputs/registry/`, `domain/registry/{verdict,governance_lookup,governance_types}.py` and the
> `model/governance/{SIGNAL_REGISTRY.md,evaluation_metadata.yaml,generate_*.py,verdict_records.py}`
> set. **Diagrams G and H below depict deleted code** and are kept only as a record of the
> pre-sweep tree; several nodes in D are likewise gone (noted per diagram). A–F are unaffected.

## Legend

```mermaid
flowchart LR
    live["live / active"]
    disc["complete-but-disconnected"]
    flight["partial / in-flight"]
    gone["superseded / archived"]
    broken["stale doc ref - broken"]
    unk["unverified ?"]

    live -->|"verified import or call"| disc
    flight -.->|"documented, no code backing"| unk

    classDef live fill:#1b5e20,stroke:#a5d6a7,stroke-width:3px,color:#ffffff
    classDef disc fill:#37474f,stroke:#b0bec5,stroke-width:1px,color:#ffffff
    classDef flight fill:#e65100,stroke:#ffcc80,stroke-width:2px,color:#ffffff
    classDef gone fill:#3e2723,stroke:#a1887f,stroke-width:1px,color:#d7ccc8
    classDef broken fill:#b71c1c,stroke:#ef9a9a,stroke-width:2px,color:#ffffff
    classDef unk fill:#4a148c,stroke:#ce93d8,stroke-width:1px,stroke-dasharray:5 3,color:#ffffff

    class live live
    class disc disc
    class flight flight
    class gone gone
    class broken broken
    class unk unk
```

| Convention | Meaning |
|---|---|
| Solid edge | Verified import or call, read in code |
| Dotted edge | Documented but unverified, or doc-claimed with no code backing |
| `?` suffix | Covered by workflow-map §5 UNVERIFIED |
| Red node | Stale doc reference from workflow-map §4 |

---

## 1. Master divergence diagram

All eight workflows and only the edges verified between them.

```mermaid
flowchart LR
    subgraph WA["A — DAL spine (shared root)"]
        dal["dal.pipeline load/run"]
    end

    subgraph WB["B — Predictive research"]
        terms["model.terms.*"]
        fc["model.predictions assemble_forecast"]
    end

    subgraph WC["C — Captaincy audit (uncommitted)"]
        cap["model.eval.captaincy_backtest"]
    end

    subgraph WF["F — Decision-as-contract (LIVE)"]
        rec["operational.recommend main"]
        eng["serve.decision_engine"]
        specs["serve captain / value / transfers"]
        out["outputs/decisions/gw N ?"]
    end

    subgraph SPINE_F["spine: domain.decision"]
        ddec["domain.decision DecisionSpec"]
    end

    subgraph WD["D — SYNTH-01 composites"]
        comp["model.assemble.composition_study"]
        gov["model.governance synth01 chain"]
    end

    subgraph SPINE_R["spine: domain.registry"]
        dreg["domain.registry.*"]
    end

    subgraph WG["G — Composite scoring CLI"]
        srun["serve.scoring.scoring_runner"]
    end

    subgraph WH["H — Weekly report CLI"]
        wrun["serve.reporting.weekly_report_runner"]
    end

    subgraph WE["E — Phase-9 monitor (archived)"]
        p9["archive.monitor.phase9_backtest"]
    end

    dal --> terms
    terms --> fc
    fc --> cap
    dal --> comp
    dal --> srun
    dal --> rec
    fc --> rec
    rec --> eng
    ddec --> eng
    eng --> specs
    specs --> out

    comp --> gov
    gov -.->|"validated (pre-ADR-011)"| p9
    dreg --> gov
    dreg --> srun
    dreg --> wrun

    gov -. "ADR-011: ranking role lost" .-> fc

    class dal live
    class terms live
    class fc live
    class rec live
    class eng live
    class specs live
    class ddec live
    class out unk
    class cap flight
    class comp disc
    class gov disc
    class dreg disc
    class srun disc
    class wrun disc
    class p9 gone

    classDef live fill:#1b5e20,stroke:#a5d6a7,stroke-width:3px,color:#ffffff
    classDef disc fill:#37474f,stroke:#b0bec5,stroke-width:1px,color:#ffffff
    classDef flight fill:#e65100,stroke:#ffcc80,stroke-width:2px,color:#ffffff
    classDef gone fill:#3e2723,stroke:#a1887f,stroke-width:1px,color:#d7ccc8
    classDef unk fill:#4a148c,stroke:#ce93d8,stroke-width:1px,stroke-dasharray:5 3,color:#ffffff
```

| Structural fact | How it reads in the diagram |
|---|---|
| A is the shared root | `dal.pipeline` fans out to B, D, F, G with no inbound edge |
| ADR-011 fork | Dotted `gov -.-> fc` labelled "ranking role lost"; D's solid edges now terminate inside D/E/G |
| ADR-012 fork | F is the only subgraph reaching `outputs/decisions`; it has no inbound edge from D |
| Two spines, no bridge | `domain.registry` feeds D/G/H only; `domain.decision` feeds F only; no edge joins the boxes |
| Live path | Green, thick-stroked chain `dal → fc → rec → eng → specs` |
| H has no DAL edge | `weekly_report_runner` imports `domain.registry`, never `dal.pipeline` |

---

## 2. Per-workflow diagrams

### A — DAL spine

```mermaid
flowchart TD
    qs["examples/quickstart.py"]
    run["dal.pipeline run"]
    load["dal.pipeline load"]
    stg["dal.staging"]
    inter["dal.intermediate"]
    fct["dal.fct"]
    feat["dal.feat feat_schema"]
    mart["dal.mart"]
    val["dal.validation"]
    art["mart parquet + manifest"]

    cB["B — model.terms"]
    cD["D — composition_study"]
    cF["F — operational.recommend"]
    cG["G — scoring_runner"]

    qs --> run
    run --> stg --> inter --> fct --> feat --> mart
    mart --> val
    val --> art
    load --> art
    art --> cB
    art --> cD
    art --> cF
    art --> cG

    class qs live
    class run live
    class load live
    class stg live
    class inter live
    class fct live
    class feat live
    class mart live
    class val live
    class art live
    class cB live
    class cD disc
    class cF live
    class cG disc

    classDef live fill:#1b5e20,stroke:#a5d6a7,stroke-width:3px,color:#ffffff
    classDef disc fill:#37474f,stroke:#b0bec5,stroke-width:1px,color:#ffffff
```

| Node | Note |
|---|---|
| `dal.mart` | Shared with G — `serve.scoring.engine` imports `POSITION_CODE_MAP` from it |
| mart artifact | Shared by all four consumers; belongs to no single workflow |

### B — Predictive research program

```mermaid
flowchart TD
    plan["docs/predictive-layer-plan.md (stale index)"]
    nb["model/terms/*/notebook.ipynb"]
    kern["research.kernels.*"]
    feats["model.features spec/build"]
    fmods["model.forecast count_models / level_estimators / shrinkage"]
    evalm["model.eval walkforward / calibration / scorer"]
    fc["model.predictions assemble_forecast"]
    cols["e_points, e_points_uncond, p10/p50/p90, p_haul"]
    docs["docs/studies/results/predictive-phase*.md"]
    nocon["no consumer — documentation only"]
    serveC["F — serve captain / value / transfers"]

    plan -.->|"index, not an import"| nb
    nb --> feats
    kern --> feats
    feats --> fmods
    fmods --> fc
    kern --> evalm
    evalm --> fc
    fc --> cols
    cols --> serveC
    evalm --> docs
    docs --> nocon

    class plan flight
    class nb live
    class kern live
    class feats live
    class fmods live
    class evalm live
    class fc live
    class cols live
    class serveC live
    class docs disc
    class nocon disc

    classDef live fill:#1b5e20,stroke:#a5d6a7,stroke-width:3px,color:#ffffff
    classDef disc fill:#37474f,stroke:#b0bec5,stroke-width:1px,color:#ffffff
    classDef flight fill:#e65100,stroke:#ffcc80,stroke-width:2px,color:#ffffff
```

| Node | Note |
|---|---|
| `research.kernels.*` | Shared with F — `kernels.inferential.resampling` reused per ADR-012 Amendment |
| `docs/predictive-layer-plan.md` | Dotted: an index doc, not a code edge; stale per map §3 divergence 5 |
| phase result docs | Terminal by design — evidence trail, no programmatic reader |

### C — Captaincy audit (in flight, uncommitted)

```mermaid
flowchart TD
    d1["predictive-phase5-captaincy-realistic-pool.md"]
    d2["predictive-phase5-captaincy-diagnostic-rerun.md"]
    d3["predictive-phase5-captaincy-by-position.md"]
    cb["model.eval.captaincy_backtest (modified)"]
    cd["model.eval.captaincy_diagnostics (modified)"]
    mt["model.eval.metrics (modified)"]
    frozen["frozen Phase-5.1 result (audited)"]
    nocon["no consumer — not linked from plan doc"]

    d1 --> d2 --> d3
    cb --> d1
    cd --> d2
    cb --> d3
    mt --> cb
    mt --> cd
    frozen -.->|"target of the audit"| d1
    d3 --> nocon

    class d1 flight
    class d2 flight
    class d3 flight
    class cb flight
    class cd flight
    class mt flight
    class frozen gone
    class nocon disc

    classDef disc fill:#37474f,stroke:#b0bec5,stroke-width:1px,color:#ffffff
    classDef flight fill:#e65100,stroke:#ffcc80,stroke-width:2px,color:#ffffff
    classDef gone fill:#3e2723,stroke:#a1887f,stroke-width:1px,color:#d7ccc8
```

| Node | Note |
|---|---|
| all three `.py` | Uncommitted working-tree modifications; shared location with B's `model/eval/` |
| frozen Phase-5.1 | Docs note frozen numbers no longer reproduce against current code |
| `model.eval.metrics` | Adds `BLOCK_GWS`, `block_bootstrap_draws` |

### D — SYNTH-01 composites

```mermaid
flowchart TD
    cs["model.assemble.composition_study"]
    recs["synth01_recommendations.yaml"]
    cands["synth01_candidates.yaml"]
    gen["model.governance generate_synth01_decisions"]
    genm["model.governance generate_evaluation_metadata"]
    prom["model.governance promote — DELETED 2026-08-16"]
    dec["synth01_decisions.yaml"]
    evalmd["evaluation_metadata.yaml"]
    reg["outputs/registry/gw36/registry.csv ?"]
    sigreg["SIGNAL_REGISTRY.md"]
    dreg["domain.registry.* (shared D/G/H)"]
    wreg["serve/weight_registry.yaml — DELETED"]
    nocon["no runtime consumer"]
    tests["tests/ only"]

    cands --> cs
    cs --> recs
    recs --> gen
    dreg --> gen
    gen --> dec
    genm --> evalmd
    prom -.-> dec
    dec --> nocon
    evalmd --> nocon
    reg --> nocon
    sigreg --> nocon
    gen --> tests
    wreg -.->|"doc claims active"| nocon

    class cs disc
    class recs disc
    class cands disc
    class gen disc
    class genm disc
    class dec disc
    class evalmd disc
    class sigreg disc
    class dreg disc
    class tests disc
    class nocon disc
    class prom unk
    class reg unk
    class wreg broken

    classDef disc fill:#37474f,stroke:#b0bec5,stroke-width:1px,color:#ffffff
    classDef broken fill:#b71c1c,stroke:#ef9a9a,stroke-width:2px,color:#ffffff
    classDef unk fill:#4a148c,stroke:#ce93d8,stroke-width:1px,stroke-dasharray:5 3,color:#ffffff
```

| Node | Note |
|---|---|
| `domain.registry.*` | Shared with G and H |
| `promotion` / `semantics` | §5 UNVERIFIED — membership inferred from a `synth01_decisions.yaml` grep, not traced per module. `promote.py` was deleted 2026-08-16 (no importer, no consumer for its `outputs/registry/` artifact); `verdict_records.py`, `generate_synth01_decisions.py`, `generate_evaluation_metadata.py`, `evaluation_metadata.yaml` and `SIGNAL_REGISTRY.md` were **deleted at `ae90398`** |
| `outputs/registry/gw36/` | **Deleted at `ae90398`** — confirmed to have no reader |
| `serve/weight_registry.yaml` | Deleted at `89a7b35`; no longer referenced from `docs/navigation-map.md` |

### E — Phase-9 monitor (archived)

```mermaid
flowchart TD
    p9["archive/monitor/phase9_backtest.py"]
    synth["D — approved SYNTH-01 compositions"]
    res["outputs/phase9_backtest_results.yaml"]
    base["outputs/operational-baseline.md"]
    stale["cites studies/operational/phase9_backtest.py — path gone"]
    nav["docs/navigation-map.md lists as current"]
    nocon["no programmatic consumer"]

    synth --> p9
    p9 --> res
    p9 --> base
    base --> stale
    nav -.->|"doc index only"| base
    res --> nocon
    base --> nocon

    class p9 gone
    class synth disc
    class res gone
    class base gone
    class nocon disc
    class nav disc
    class stale broken

    classDef disc fill:#37474f,stroke:#b0bec5,stroke-width:1px,color:#ffffff
    classDef gone fill:#3e2723,stroke:#a1887f,stroke-width:1px,color:#d7ccc8
    classDef broken fill:#b71c1c,stroke:#ef9a9a,stroke-width:2px,color:#ffffff
```

| Node | Note |
|---|---|
| stale path | `studies/` did not survive the `research/` migration; real file is `archive/monitor/phase9_backtest.py` |

### F — Decision-as-contract runtime (the live path)

```mermaid
flowchart TD
    cli["operational/recommend.py main --target-gw"]
    bt["operational/backtest.py backtest_decision"]
    dload["dal.pipeline load (A)"]
    fc["model.predictions assemble_forecast (B)"]
    ddec["domain.decision DecisionSpec"]
    eng["serve.decision_engine run_decision"]
    cap["serve.captain CAPTAIN"]
    val["serve.value VALUE"]
    tr["serve.transfers TRANSFERS"]
    avail["serve.availability"]
    ic["serve.input_contracts"]
    edec["model.eval.decision spec/backtest/baselines/metrics"]
    kern["research.kernels.inferential.resampling (B)"]
    out["outputs/decisions/gw N csv + md ?"]
    br["BacktestResult in-memory — no persisted artifact"]

    cli --> dload
    cli --> fc
    cli --> ddec
    cli --> eng
    ddec --> eng
    eng --> cap
    eng --> val
    eng --> tr
    ic --> eng
    avail --> eng
    cap --> out
    val --> out
    tr --> out

    bt --> edec
    bt --> cap
    bt --> val
    bt --> tr
    kern --> edec
    edec --> br

    class cli live
    class bt live
    class dload live
    class fc live
    class ddec live
    class eng live
    class cap live
    class val live
    class tr live
    class avail live
    class ic live
    class edec live
    class kern live
    class br live
    class out unk

    classDef live fill:#1b5e20,stroke:#a5d6a7,stroke-width:3px,color:#ffffff
    classDef unk fill:#4a148c,stroke:#ce93d8,stroke-width:1px,stroke-dasharray:5 3,color:#ffffff
```

| Node | Note |
|---|---|
| `dal.pipeline load`, `assemble_forecast` | Shared with A and B respectively |
| `research.kernels.inferential.resampling` | Shared with B |
| `outputs/decisions/gw N` | §5 UNVERIFIED — directory absent, `outputs/*` gitignored; no evidence the runner has produced persisted output |
| `serve.captain/value/transfers` | Shared with the backtest path — same `rank_*` functions injected as `pick_fn` |

### G — Composite scoring CLI — **REMOVED at `ae90398`** (historical diagram)

```mermaid
flowchart TD
    run["serve/scoring/scoring_runner.py (argparse)"]
    dload["dal.pipeline load (A)"]
    sel["serve.scoring.signal_selector load_manifest_from_path"]
    dver["domain.registry.verdict (shared D/G/H)"]
    dlay["domain.signal_layers"]
    con["serve.scoring.contracts"]
    engine["serve.scoring.engine score"]
    mart["dal.mart POSITION_CODE_MAP (A)"]
    rend["serve.scoring.renderer render"]
    outp["rendered scorer output"]
    tests["tests/ only — no module imports serve.scoring"]
    manifest["SignalManifest input ?"]

    run --> dload
    run --> sel
    sel --> dver
    sel --> dlay
    sel --> con
    manifest -.-> sel
    run --> engine
    engine --> mart
    engine --> con
    run --> rend
    rend --> outp
    outp --> tests

    class run disc
    class dload live
    class sel disc
    class dver disc
    class dlay disc
    class con disc
    class engine disc
    class mart live
    class rend disc
    class outp disc
    class tests disc
    class manifest unk

    classDef live fill:#1b5e20,stroke:#a5d6a7,stroke-width:3px,color:#ffffff
    classDef disc fill:#37474f,stroke:#b0bec5,stroke-width:1px,color:#ffffff
    classDef unk fill:#4a148c,stroke:#ce93d8,stroke-width:1px,stroke-dasharray:5 3,color:#ffffff
```

| Node | Note |
|---|---|
| `dal.pipeline load`, `dal.mart` | Shared with A |
| `domain.registry.verdict` | Shared with D and H |
| SignalManifest input | Moot — the whole package and its tests were deleted at `ae90398` |
| consumers | Were `tests/test_scorer_engine.py`, `test_registry_lifecycle.py`, `test_runtime_metadata_propagation.py` — all deleted at `ae90398` |

### H — Weekly report CLI — **REMOVED at `ae90398`** (historical diagram)

```mermaid
flowchart TD
    run["serve/reporting/weekly_report_runner.py main / run_week"]
    lreg["domain.registry.operational load_registry (shared D/G/H)"]
    vreg["domain.registry.validation validate_registry_contract"]
    icw["serve.reporting.insight_card_writer"]
    reps["serve.reporting.reports"]
    snaps["serve.reporting.snapshots"]
    schema["domain.registry.schema PRIMARY_KEY_COLUMNS"]
    si["serve.reporting.signal_intelligence — pathlib + pandas only"]
    cards["insight_cards.csv + report/snapshot files"]
    tests["tests/ only"]
    dg["tests/test_downstream_governance.py — sole allowed re-export exception"]

    run --> lreg
    run --> vreg
    run --> icw
    icw --> cards
    reps --> cards
    snaps --> schema
    snaps --> cards
    cards --> tests
    run --> dg

    class run disc
    class lreg disc
    class vreg disc
    class icw disc
    class reps disc
    class snaps disc
    class schema disc
    class si disc
    class cards disc
    class tests disc
    class dg disc

    classDef disc fill:#37474f,stroke:#b0bec5,stroke-width:1px,color:#ffffff
```

| Node | Note |
|---|---|
| `domain.registry.*` | Shared with D and G |
| `signal_intelligence` | Drawn unconnected — imports only `pathlib` and `pandas`; despite the name, no edge to retired signal machinery |
| no DAL edge | This workflow reads the registry, never `dal.pipeline` |

---

## 3. Fork-point timeline

```mermaid
timeline
    title Decision points that moved workflow boundaries
    section Composite era
        2026-05-26 : ADR-002 additive weighted scoring — starts D, governs scoring_runner and weight_registry
        2026-06-05 : ADR-009 unified evaluation provenance — binds research, model.governance, serve.scoring.signal_selector
        2026-06-05 : ADR-010 layered decision authority — generalizes provenance to every decision type across domain, research, model, serve
    section Forecast cutover
        2026-08-01 : ADR-011 model forecast supersedes composites — B/F take D's ranking role, weight_registry and provenance deleted, D study remains (CLI deleted 2026-08-15 at ae90398)
    section Contract era
        2026-08-05 : ADR-012 decision as first-class contract — starts F, builds the runner ADR-011 only described, empties tests/helpers
        2026-08-14 : Workflow C captaincy audit — uncommitted, re-audits Door 1 off B's Phase 5.1, not folded into the plan doc
```

| Date | ADR / event | Started | Displaced |
|---|---|---|---|
| 2026-05-26 | ADR-002 | D — composite scoring, `weight_registry.yaml` locked | — (both retired: `89a7b35`, `ae90398`) |
| 2026-06-05 | ADR-009 | Shared provenance across research / governance / `serve.scoring` | Ad-hoc per-study provenance |
| 2026-06-05 | ADR-010 | `domain.registry` spine for D/G/H | Implicit single-slot "one true source per decision" |
| 2026-08-01 | ADR-011 (`06aa438`) | B's forecast feeding serve rankers | D's ranking role; `weight_registry.{yaml,py}` + `provenance.py` deleted; D's study left in place, its governance chain and `serve/scoring` CLI deleted at `ae90398` |
| 2026-08-05 | ADR-012 (`c475873`) | F — `DecisionSpec`, `serve.decision_engine`, `model/eval/decision/` | The runner ADR-011 referred to but never built; `tests/helpers/*` emptied to `__init__.py` |
| 2026-08-14 | Workflow C | Captaincy pool re-audit, three result docs | Nothing — diverges from B's stated "Door 2" resume pointer without replacing it |

ADR dates are the `Date:` field in each ADR; commit hashes are the commit that introduced or
superseded the file (`git log -1` per path). ADR-002's file is dated 2026-08-01 in git because
`06aa438` rewrote its header to record supersession.
