# Stage 5 power simulation lab -- extra-large shock probe

Conditional on assumed settings (shock, manager spread, tie rate, independence beyond the weekly shock); not measured from real data.

Probe: a 9-point gameweek shock (an assumption) on no-edge cells (true 50%), 1,000 fake studies each, against N2's count: at most 63 family-wise firings. Reported alongside; it never invalidates a count.

| Anchor | Gameweeks | Family-wise firings | Over the limit |
|---|---|---|---|
| worst_case_corner | 8 | 62 of 1,000 | no |
| worst_case_corner | 12 | 39 of 1,000 | no |
| worst_case_corner | 16 | 38 of 1,000 | no |
| baseline | 8 | 57 of 1,000 | no |
| baseline | 12 | 37 of 1,000 | no |
| baseline | 16 | 34 of 1,000 | no |

- worst_case_corner: no probed count over the limit
- baseline: no probed count over the limit

## Largest tolerable gameweek shock per count

- 5 gameweeks: no level (verdict procedure invalid at this count)
- 8 gameweeks: 9 points
- 12 gameweeks: 9 points
- 16 gameweeks: 9 points
- 24 gameweeks: 6 points, not probed at 9
- 38 gameweeks: 6 points, not probed at 9
