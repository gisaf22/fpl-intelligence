from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

from dal.curated.player_gameweek_spine import build_player_gameweek_spine

SIGNAL_ID = "FORM-001"
SIGNAL = "assists"
POSITION = "MID"
TARGET = "total_points"
MINUTES_THRESHOLD = 60

DB_PATH = Path(os.environ.get("FPL_DB_PATH", "~/.fpl/fpl.db")).expanduser()


def run(db_path: Path = DB_PATH) -> Path:
    spine = build_player_gameweek_spine(db_path)
    mid = spine[
        (spine["position_label"] == POSITION)
        & spine["minutes"].notna()
        & (spine["minutes"] >= MINUTES_THRESHOLD)
    ].copy()

    rho, pvalue = spearmanr(mid[SIGNAL].fillna(0), mid[TARGET])

    artifact = pd.DataFrame([{
        "signal_id": SIGNAL_ID,
        "signal": SIGNAL,
        "position": POSITION,
        "rho_pooled": round(float(rho), 4),
        "pvalue": round(float(pvalue), 8),
        "n_records": len(mid),
        "minutes_threshold": MINUTES_THRESHOLD,
        "data_cutoff_gw": int(mid["gw"].max()),
    }])

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path("studies/runs") / f"{SIGNAL_ID}_{ts}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    artifact.to_csv(out, index=False)

    print(f"{SIGNAL_ID} | {SIGNAL} | {POSITION} | rho={rho:.4f} | p={pvalue:.2e} | n={len(mid)}")
    return out


if __name__ == "__main__":
    run()
