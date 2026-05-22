import pandas as pd

from signals.lifecycle import load_registry
from intelligence.reporting.snapshots import (
    SNAPSHOT_CHANGE_COLUMNS,
    build_snapshot_changes,
    default_previous_snapshot_path,
    write_snapshot_changes,
)


def test_default_previous_snapshot_path_uses_prior_gameweek_folder(tmp_path):
    output_dir = tmp_path / "gw36"

    assert default_previous_snapshot_path(36, output_dir) == (
        tmp_path / "gw35" / "registry_snapshot.csv"
    )
    assert default_previous_snapshot_path(1, tmp_path / "gw1") is None


def test_snapshot_changes_marks_baseline_without_previous_snapshot():
    current = load_registry()

    changes = build_snapshot_changes(
        current_snapshot=current,
        previous_snapshot=None,
        gw=10,
    )

    assert list(changes.columns) == list(SNAPSHOT_CHANGE_COLUMNS)
    assert len(changes) == 1
    assert changes.loc[0, "change_type"] == "baseline"
    assert changes.loc[0, "current_value"] == "116 rows"


def test_snapshot_changes_detects_governance_transitions_by_key_not_row_order():
    previous = load_registry()
    current = previous.copy()
    target = (
        current["signal"].eq("xgi")
        & current["position"].eq("MID")
        & current["population_scope"].eq("primary")
    )

    previous.loc[target, "downstream_status"] = "caveated"
    previous.loc[target, "relationship_geometry"] = "threshold_positive"
    previous.loc[target, "low_confidence"] = True
    previous.loc[target, "support_type"] = "sparse_event_process"

    current.loc[target, "downstream_status"] = "eligible"
    current.loc[target, "relationship_geometry"] = "monotonic_positive"
    current.loc[target, "low_confidence"] = False
    current.loc[target, "support_type"] = "insufficient_n"
    current = current.sample(frac=1, random_state=7).reset_index(drop=True)

    changes = build_snapshot_changes(
        current_snapshot=current,
        previous_snapshot=previous,
        gw=36,
        previous_gw=35,
    )
    changed_target = changes[
        changes["signal"].eq("xgi")
        & changes["position"].eq("MID")
        & changes["population_scope"].eq("primary")
    ]

    assert {
        "newly_eligible",
        "changed_geometry",
        "changed_confidence_caveat",
        "changed_support_type",
    }.issubset(set(changed_target["change_type"]))
    assert "downstream_status" in set(changed_target["field"])
    assert changed_target["previous_downstream_status"].eq("caveated").all()
    assert changed_target["current_downstream_status"].eq("eligible").all()


def test_write_snapshot_changes_uses_previous_snapshot_when_available(tmp_path):
    previous = load_registry()
    current = previous.copy()
    target = current["signal"].eq("minutes") & current["position"].eq("GK")
    previous.loc[target, "downstream_status"] = "caveated"
    current.loc[target, "downstream_status"] = "blocked"

    previous_dir = tmp_path / "gw35"
    previous_dir.mkdir()
    previous.to_csv(previous_dir / "registry_snapshot.csv", index=False)

    output_path = write_snapshot_changes(
        current_snapshot=current,
        gw=36,
        output_dir=tmp_path / "gw36",
    )

    assert output_path.exists()
    changes = pd.read_csv(output_path)
    assert "newly_blocked" in set(changes["change_type"])
