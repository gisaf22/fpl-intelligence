"""The Model + Term contracts (spec §2) — the interfaces that kill the god-files.

Splitting ``Model`` (fittable) from ``Term`` (a scored view it emits) is what lets a *joint* model
fit once and emit several terms. The contracts are ``Protocol``s so a term folder satisfies them
structurally — no base-class inheritance, no registry edits — plus small frozen result records so
every term reports assumptions / gate / diagnostics in the same shape.

Data-science checks have fixed homes on the timeline (spec §4):

* **pre-fit** — :meth:`Model.check_assumptions` → :class:`AssumptionReport` (dispersion: is the family
  justified? detectability: is the effect learnable at this N?). A term that fails here is
  *inconclusive*, never abandoned.
* **fit** — :meth:`Model.fit` → :class:`Fitted` (walk-forward; window/penalty tuned in the inner split).
* **emit** — :meth:`Model.emit` → ``{term_name: prediction}`` (one+ terms; joint models emit many).
* **gate** — :meth:`Term.validate` → :class:`GateResult` vs the term's own baseline (shared eval scorer).
* **diagnose** — :meth:`Term.diagnose` → :class:`Diagnostics` (residual/error analysis + ablation), post-gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

from model.features.spec import FeaturePool, Grain


@dataclass(frozen=True)
class Hypothesis:
    """A pre-registered claim (spec §7): the success threshold is written **before** the run.

    ``status`` moves open → supported/refuted/inconclusive only after the gate; a null needs the
    detectability floor cleared first (else it stays inconclusive).
    """

    claim: str
    test: str
    success_threshold: str
    due_by: str = ""
    status: str = "open"


@dataclass(frozen=True)
class AssumptionReport:
    """Pre-fit verdict: is the family justified and the effect learnable at this N? (spec §4 stage 1)."""

    term: str
    dispersion: dict[str, float | str]  # index of dispersion, family recommendation, per §count_models
    detectable: bool                    # detectability floor cleared (enough events/rows to learn the effect)
    n_train: int
    notes: str = ""

    @property
    def family_ok(self) -> bool:
        """Whether the chosen family matches the dispersion diagnosis (recommendation == chosen)."""
        return self.dispersion.get("family_ok", True) is True


@dataclass(frozen=True)
class Fitted:
    """A fitted model bundle carried from ``fit`` to ``emit`` (opaque to callers)."""

    name: str
    predictions: pd.Series          # emitted prediction indexed to the scored rows (mart index)
    features: tuple[str, ...]       # the design columns actually used
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GateResult:
    """A term's per-position gate vs its own baseline (spec §5, shared eval scorer).

    **Two criteria, because they fail independently.** ``passed`` is the *ranking* gate (does the
    signal out-rank the term's own naive history?). ``passed_calibration`` is the *level* gate (does
    the term predict the right AMOUNT?). A model can rank a position perfectly and still be
    systematically wrong about how many goals/points it produces — ranking metrics are invariant to
    any monotone level error, so the ranking gate is structurally blind to it. Composition and
    cross-position comparison depend on the level, so it gets its own criterion rather than riding
    along on Spearman.
    """

    term: str
    table: pd.DataFrame             # per-position spearman for {baseline, model} on the common eval set
    passed: dict[str, bool]         # position -> model beats its own baseline (RANKING)
    calibration: pd.DataFrame = field(default_factory=pd.DataFrame)  # per-position bias (metrics.position_bias)
    passed_calibration: dict[str, bool] = field(default_factory=dict)  # position -> no material level bias

    @property
    def passed_all(self) -> dict[str, bool]:
        """Per-position verdict on BOTH criteria — a term is only sound where it ranks *and* levels."""
        return {p: bool(ok and self.passed_calibration.get(p, True)) for p, ok in self.passed.items()}


@dataclass(frozen=True)
class Diagnostics:
    """Post-gate residual/error analysis + ablation (spec §4 stage 5, §7)."""

    term: str
    residuals: pd.DataFrame         # which players/GWs the model misses worst
    ablation: pd.DataFrame          # drop each feature, re-gate: measured contribution


@runtime_checkable
class Model(Protocol):
    """The fittable unit (one folder). Draws a *minimal* and a *selected* model from one pool."""

    name: str
    pool: FeaturePool               # the single candidate pool (minimal + selected draw from it)
    grain: Grain                    # the grain it is fit at (drives the join/broadcast)
    hypotheses: tuple[Hypothesis, ...]

    def check_assumptions(self, train: pd.DataFrame) -> AssumptionReport: ...
    def fit(self, mart: pd.DataFrame) -> Fitted: ...
    def emit(self, fitted: Fitted) -> dict[str, np.ndarray]: ...


@runtime_checkable
class Term(Protocol):
    """A scored quantity a Model emits (a view on its output; joint models share the model)."""

    name: str
    model: Model
    baseline_col: str               # its OWN naive bar (spec §5, per-term level)

    def validate(self, mart: pd.DataFrame) -> GateResult: ...
    def diagnose(self, mart: pd.DataFrame) -> Diagnostics: ...
