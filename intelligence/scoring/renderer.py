"""HTML renderer — accepts ScorerOutput, returns a self-contained HTML string.

No business logic. No signal selection. No scoring.
All CSS and JS is inlined. No external dependencies.
"""

from __future__ import annotations

import html
from collections import defaultdict

from intelligence.scoring.contracts import ConfirmedSignal, PlayerScore, ScorerOutput

_POSITIONS: tuple[str, ...] = ("GK", "DEF", "MID", "FWD")

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #f8f9fa;
  --surface: #ffffff;
  --border: #dee2e6;
  --text: #212529;
  --muted: #6c757d;
  --teal: #0d9488;
  --teal-bg: #ccfbf1;
  --amber: #d97706;
  --amber-bg: #fef3c7;
  --bar-pos: #0d9488;
  --bar-neg: #dc2626;
  --tab-active: #0d9488;
  --tab-active-text: #ffffff;
  --shadow: rgba(0,0,0,0.06);
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111827;
    --surface: #1f2937;
    --border: #374151;
    --text: #f9fafb;
    --muted: #9ca3af;
    --teal: #2dd4bf;
    --teal-bg: #134e4a;
    --amber: #fbbf24;
    --amber-bg: #451a03;
    --bar-pos: #2dd4bf;
    --bar-neg: #f87171;
    --tab-active: #2dd4bf;
    --tab-active-text: #111827;
    --shadow: rgba(0,0,0,0.3);
  }
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 14px;
  background: var(--bg);
  color: var(--text);
  padding: 1.5rem;
  line-height: 1.5;
}

.header {
  margin-bottom: 1.5rem;
}

.header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
}

.header .meta {
  color: var(--muted);
  font-size: 0.85rem;
}

.scope-notice {
  margin-top: 0.75rem;
  padding: 0.6rem 1rem;
  background: var(--amber-bg);
  border-left: 3px solid var(--amber);
  border-radius: 4px;
  color: var(--text);
  font-size: 0.85rem;
  font-style: italic;
}

.tabs {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1rem;
  border-bottom: 2px solid var(--border);
  padding-bottom: 0;
}

.tab-btn {
  padding: 0.5rem 1.25rem;
  border: 1px solid var(--border);
  border-bottom: none;
  background: var(--surface);
  color: var(--muted);
  cursor: pointer;
  border-radius: 6px 6px 0 0;
  font-size: 0.9rem;
  font-weight: 600;
  transition: all 0.15s;
}

.tab-btn:hover { background: var(--bg); }

.tab-btn.active {
  background: var(--tab-active);
  color: var(--tab-active-text);
  border-color: var(--tab-active);
}

.tab-panel { display: none; }
.tab-panel.active { display: block; }

.table-wrap {
  overflow-x: auto;
  border-radius: 8px;
  box-shadow: 0 1px 3px var(--shadow);
  margin-bottom: 1.5rem;
}

table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
}

thead th {
  background: var(--surface);
  padding: 0.6rem 0.75rem;
  text-align: left;
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
  border-bottom: 2px solid var(--border);
  white-space: nowrap;
}

thead th.rank-col { width: 3rem; text-align: center; }
thead th.score-col { width: 6rem; text-align: center; }
thead th.signal-col { min-width: 100px; }

tbody tr:hover { background: var(--bg); }

td {
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}

td.rank-cell {
  text-align: center;
  font-weight: 700;
  font-size: 1.05rem;
  color: var(--teal);
}

td.score-cell {
  text-align: center;
  font-weight: 600;
  font-size: 1.1rem;
}

td.name-cell { font-weight: 500; }

.badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  vertical-align: middle;
  margin-left: 0.25rem;
  letter-spacing: 0.02em;
}

.badge-core {
  background: var(--teal-bg);
  color: var(--teal);
  border: none;
}

.badge-review {
  background: transparent;
  color: var(--amber);
  border: 1px solid var(--amber);
}

/* Direction bar */
.bar-cell { min-width: 100px; padding: 0.4rem 0.75rem; }

.bar-wrap {
  position: relative;
  height: 14px;
  background: var(--bg);
  border-radius: 3px;
  overflow: visible;
}

/* Vertical centerline */
.bar-wrap::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--border);
  transform: translateX(-50%);
}

.bar-fill {
  position: absolute;
  top: 2px;
  bottom: 2px;
  border-radius: 2px;
}

.bar-fill.pos {
  left: 50%;
  background: var(--bar-pos);
}

.bar-fill.neg {
  right: 50%;
  background: var(--bar-neg);
}

.bar-raw {
  font-size: 0.72rem;
  color: var(--muted);
  margin-top: 2px;
  text-align: center;
}

/* Caveated section */
.caveated-section {
  margin-top: 1rem;
}

.caveated-section h3 {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--muted);
  margin-bottom: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.caveated-list {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.caveated-item {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.3rem 0.6rem;
  font-size: 0.8rem;
}

.caveated-item strong { color: var(--text); }
.caveated-item .reason { color: var(--muted); }

.signal-meta {
  font-size: 0.70rem;
  font-weight: 400;
  color: var(--muted);
  letter-spacing: 0;
  text-transform: none;
}

.methodology-note {
  margin-top: 0.5rem;
  margin-bottom: 1rem;
  padding: 0.5rem 0.9rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 0.82rem;
  color: var(--muted);
}
"""

_JS = """
function showTab(position) {
  document.querySelectorAll('.tab-btn').forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.pos === position);
  });
  document.querySelectorAll('.tab-panel').forEach(function(panel) {
    panel.classList.toggle('active', panel.dataset.pos === position);
  });
}
"""


def _fmt(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{decimals}f}"


def _bar_html(normalised: float | None, direction: int) -> str:
    if normalised is None:
        return '<div class="bar-wrap"></div>'
    pct = max(0.0, min(1.0, normalised)) * 50  # 0–50% of cell width
    if direction > 0:
        fill = f'<div class="bar-fill pos" style="width:{pct:.1f}%"></div>'
    else:
        fill = f'<div class="bar-fill neg" style="width:{pct:.1f}%"></div>'
    return f'<div class="bar-wrap">{fill}</div>'


def _badge(promotion_class: str) -> str:
    if promotion_class == "core_signal":
        return '<span class="badge badge-core">core</span>'
    if promotion_class == "review_signal":
        return '<span class="badge badge-review">review</span>'
    return ""


def _render_position_table(
    position: str,
    players: list[PlayerScore],
    confirmed_for_pos: list[ConfirmedSignal],
    caveated_for_pos: list,
) -> str:
    if not players:
        return f"<p style='color:var(--muted); padding:1rem;'>No data for {position}.</p>"

    # Sort players by rank, then by player_id as tiebreaker
    players_sorted = sorted(players, key=lambda p: (p.rank, p.player_id))

    # Table header
    th_signals = ""
    for sig in confirmed_for_pos:
        badge = _badge(sig.promotion_class)
        direction_arrow = "↑" if sig.direction > 0 else "↓"
        rho_display = f"{abs(sig.rho_pooled):.2f}"
        th_signals += (
            f'<th class="signal-col">'
            f'{html.escape(sig.signal)}{badge}'
            f'<br><span class="signal-meta">{direction_arrow} ρ={rho_display}</span>'
            f'</th>'
        )

    header = (
        f'<thead><tr>'
        f'<th class="rank-col">Rank</th>'
        f'<th>Player</th>'
        f'<th class="score-col">Score</th>'
        f'{th_signals}'
        f'</tr></thead>'
    )

    rows = ""
    for p in players_sorted:
        score_display = f"{p.composite_score * 10:.1f}"
        td_signals = ""
        for sig in confirmed_for_pos:
            raw_val = p.signal_values.get(sig.signal)
            norm_val = p.signal_normalised.get(sig.signal)
            bar = _bar_html(norm_val, sig.direction)
            raw_str = _fmt(raw_val, 2) if raw_val is not None else "—"
            td_signals += (
                f'<td class="bar-cell">'
                f'{bar}'
                f'<div class="bar-raw">{html.escape(raw_str)}</div>'
                f'</td>'
            )

        rows += (
            f'<tr>'
            f'<td class="rank-cell">{p.rank}</td>'
            f'<td class="name-cell">{html.escape(p.player_name)}</td>'
            f'<td class="score-cell">{score_display}</td>'
            f'{td_signals}'
            f'</tr>'
        )

    table_html = (
        f'<div class="table-wrap">'
        f'<table>{header}<tbody>{rows}</tbody></table>'
        f'</div>'
    )

    # Caveated signals section
    caveated_html = ""
    if caveated_for_pos:
        items = ""
        for sig in caveated_for_pos:
            items += (
                f'<li class="caveated-item">'
                f'<strong>{html.escape(sig.signal)}</strong> '
                f'<span class="reason">— {html.escape(sig.reason)}</span>'
                f'</li>'
            )
        caveated_html = (
            f'<div class="caveated-section">'
            f'<h3>Excluded signals</h3>'
            f'<ul class="caveated-list">{items}</ul>'
            f'</div>'
        )

    return table_html + caveated_html


def render(output: ScorerOutput) -> str:
    """Return a complete self-contained HTML string for the given ScorerOutput."""
    manifest = output.manifest

    # Index confirmed and caveated signals by position
    confirmed_by_pos: dict[str, list[ConfirmedSignal]] = defaultdict(list)
    for sig in manifest.confirmed:
        confirmed_by_pos[sig.position].append(sig)

    caveated_by_pos: dict[str, list] = defaultdict(list)
    for sig in manifest.caveated:
        caveated_by_pos[sig.position].append(sig)

    # Index players by position
    players_by_pos: dict[str, list[PlayerScore]] = defaultdict(list)
    for p in output.players:
        players_by_pos[p.position].append(p)

    # Build tabs — only for positions that appear in manifest.confirmed
    active_positions = [p for p in _POSITIONS if p in confirmed_by_pos]
    if not active_positions:
        active_positions = [p for p in _POSITIONS if p in players_by_pos] or list(_POSITIONS)

    tab_buttons = ""
    tab_panels = ""
    for i, pos in enumerate(active_positions):
        is_active = i == 0
        active_cls = " active" if is_active else ""
        tab_buttons += (
            f'<button class="tab-btn{active_cls}" data-pos="{pos}" '
            f'onclick="showTab(\'{pos}\')">{pos}</button>'
        )
        content = _render_position_table(
            position=pos,
            players=players_by_pos.get(pos, []),
            confirmed_for_pos=confirmed_by_pos.get(pos, []),
            caveated_for_pos=caveated_by_pos.get(pos, []),
        )
        tab_panels += f'<div class="tab-panel{active_cls}" data-pos="{pos}">{content}</div>'

    scored_at_display = output.scored_at.replace("T", " ").replace("+00:00", " UTC")

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GW{output.gw} Player Scores — FPL Intelligence</title>
<style>{_CSS}</style>
</head>
<body>
<div class="header">
  <h1>GW{output.gw} Player Scores</h1>
  <div class="meta">Scored at {html.escape(scored_at_display)}</div>
  <div class="scope-notice">
    This ranks players by historical signal associations. It is not a prediction.
  </div>
  <div class="methodology-note">
    Score = weighted mean of normalised signal values, weight = |ρ| (Spearman rank correlation
    with GW total points). Signals shown are lifecycle-promoted (core_signal or review_signal)
    with |ρ| ≥ 0.15. Higher score = stronger historical signal alignment. Not a prediction.
  </div>
</div>
<div class="tabs">{tab_buttons}</div>
{tab_panels}
<script>{_JS}</script>
</body>
</html>"""

    return doc
