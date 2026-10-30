# Stage 5 power simulation lab -- report

Conditional on assumed settings (shock, manager spread, tie rate, independence beyond the weekly shock); not measured from real data.

## Assumptions (not measurements)

- Gameweek shock sizes, SD of a gameweek's true win share in points: small 2, medium 4, large 6 (assumption).
- Manager effect sizes, SD of a manager's true win share in points: small 5, medium 10, large 15 (assumption).
- Fake managers: every manager plays every gameweek; bands are equal thirds fixed per manager (assumption).
- 1,000 fake studies per setting; 10,000 inner bootstrap repeats; two-sided p-value (1 + k) / (1 + B), unrounded.
- False-alarm check (N2): at most 63 family-wise firings of 1,000 at a true 50%, at every setting; gated per gameweek count (U5).
- Sensitivity check: power at least 0.99 at a true 65% at the worst_case_corner (a judgement).
- P6's 100,000-repeat re-run is not applied in the lab: 7,290 fake studies would have triggered one.

## Failed checks

- false-alarm check failed: baseline fired in 68 of 1000
- false-alarm check failed: shock_large fired in 92 of 1000
- false-alarm check failed: manager_effect_small fired in 76 of 1000
- false-alarm check failed: ties_20 fired in 68 of 1000
- false-alarm check failed: ties_60 fired in 66 of 1000
- false-alarm check failed: worst_case_corner fired in 101 of 1000
- false-alarm check failed: worst_case_corner_managers_1000 fired in 74 of 1000

## MDE at the smallest valid gameweek count (P10, D-P10)

- MDE 55% at 8 gameweeks, read at worst_case_corner_gameweeks_8 (that count's lowest-power setting); labels: none.

## Gameweeks needed (output a)

- 8 gameweeks for 80% power at a true 55%.
- 24 gameweeks for 80% power at a true 53%.

### Largest tolerable gameweek shock per count (#65 probe)

- 5 gameweeks: no level (verdict procedure invalid at this count)
- 8 gameweeks: 9 points
- 12 gameweeks: 9 points
- 16 gameweeks: 9 points
- 24 gameweeks: 6 points, not probed at 9
- 38 gameweeks: 6 points, not probed at 9

## Extra-large shock probe (#65)

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

## MDE per gameweek count (output b)

| Gameweeks | Read at | Power at 55% | MDE | Label | 55% detectable | 53% detectable |
|---|---|---|---|---|---|---|
| 5 | shock_large | - | not defined at this count | verdict procedure invalid at this count (false-alarm check failed) | - | - |
| 8 | worst_case_corner_gameweeks_8 | 0.821 | 55% | none | yes | no |
| 12 | worst_case_corner_gameweeks_12 | 0.957 | 55% | none | yes | no |
| 16 | worst_case_corner_gameweeks_16 | 0.993 | 55% | none | yes | no |
| 24 | gameweeks_24 | 1.000 | 53% | none | yes | yes |
| 38 | gameweeks_38 | 1.000 | 53% | none | yes | yes |

## Power against managers, and manager-week rows (outputs c, d)

| Setting | Managers | Gameweeks | Rows | Power at 55% |
|---|---|---|---|---|
| baseline | 2,000 | 5 | 10,000 | invalid |
| shock_small | 2,000 | 5 | 10,000 | invalid |
| shock_large | 2,000 | 5 | 10,000 | invalid |
| manager_effect_small | 2,000 | 5 | 10,000 | invalid |
| manager_effect_large | 2,000 | 5 | 10,000 | invalid |
| ties_20 | 2,000 | 5 | 10,000 | invalid |
| ties_60 | 2,000 | 5 | 10,000 | invalid |
| gameweeks_8 | 2,000 | 8 | 16,000 | 0.881 |
| gameweeks_12 | 2,000 | 12 | 24,000 | 0.980 |
| gameweeks_16 | 2,000 | 16 | 32,000 | 0.999 |
| gameweeks_24 | 2,000 | 24 | 48,000 | 1.000 |
| gameweeks_38 | 2,000 | 38 | 76,000 | 1.000 |
| managers_500 | 500 | 5 | 2,500 | invalid |
| managers_1000 | 1,000 | 5 | 5,000 | invalid |
| worst_case_corner | 2,000 | 5 | 10,000 | invalid |
| worst_case_corner_gameweeks_8 | 2,000 | 8 | 16,000 | 0.821 |
| worst_case_corner_gameweeks_12 | 2,000 | 12 | 24,000 | 0.957 |
| worst_case_corner_gameweeks_16 | 2,000 | 16 | 32,000 | 0.993 |
| worst_case_corner_gameweeks_24 | 2,000 | 24 | 48,000 | 1.000 |
| worst_case_corner_gameweeks_38 | 2,000 | 38 | 76,000 | 1.000 |
| worst_case_corner_managers_500 | 500 | 5 | 2,500 | invalid |
| worst_case_corner_managers_1000 | 1,000 | 5 | 5,000 | invalid |

## p-value resolution (output e)

Method: exact enumeration of the gameweek resampling: G gameweeks drawn with replacement give C(2G-1, G) distinct multisets; the smallest step a two-sided p-value can take from them is 2 / G^G (all G draws the same gameweek), and the Monte Carlo floor is 2 / (B + 1); the threshold is reachable when both are at or below Holm's strictest threshold.

| Gameweeks | Inner repeats | Distinct gameweek resamples | Smallest step | Monte Carlo floor | 0.0125 reachable |
|---|---|---|---|---|---|
| 5 | 10,000 | 126 | 0.00064 | 0.0002 | yes |
| 8 | 10,000 | 6,435 | 1.19e-07 | 0.0002 | yes |
| 12 | 10,000 | 1,352,078 | 2.24e-13 | 0.0002 | yes |
| 16 | 10,000 | 300,540,195 | 1.08e-19 | 0.0002 | yes |
| 24 | 10,000 | 16,123,801,841,550 | 1.5e-33 | 0.0002 | yes |
| 38 | 10,000 | 3,446,310,324,346,630,677,300 | 1.86e-60 | 0.0002 | yes |

## Power by setting and true win share

| Setting | Gameweeks | 51% | 52% | 53% | 55% | 58% | 60% |
|---|---|---|---|---|---|---|---|
| baseline | 5 | invalid | invalid | invalid | invalid | invalid | invalid |
| shock_small | 5 | invalid | invalid | invalid | invalid | invalid | invalid |
| shock_large | 5 | invalid | invalid | invalid | invalid | invalid | invalid |
| manager_effect_small | 5 | invalid | invalid | invalid | invalid | invalid | invalid |
| manager_effect_large | 5 | invalid | invalid | invalid | invalid | invalid | invalid |
| ties_20 | 5 | invalid | invalid | invalid | invalid | invalid | invalid |
| ties_60 | 5 | invalid | invalid | invalid | invalid | invalid | invalid |
| gameweeks_8 | 8 | 0.078 | 0.221 | 0.463 | 0.881 | 0.999 | 1.000 |
| gameweeks_12 | 12 | 0.084 | 0.300 | 0.626 | 0.980 | 1.000 | 1.000 |
| gameweeks_16 | 16 | 0.117 | 0.349 | 0.748 | 0.999 | 1.000 | 1.000 |
| gameweeks_24 | 24 | 0.127 | 0.507 | 0.906 | 1.000 | 1.000 | 1.000 |
| gameweeks_38 | 38 | 0.178 | 0.748 | 0.990 | 1.000 | 1.000 | 1.000 |
| managers_500 | 5 | invalid | invalid | invalid | invalid | invalid | invalid |
| managers_1000 | 5 | invalid | invalid | invalid | invalid | invalid | invalid |
| worst_case_corner | 5 | invalid | invalid | invalid | invalid | invalid | invalid |
| worst_case_corner_gameweeks_8 | 8 | 0.079 | 0.215 | 0.434 | 0.821 | 0.996 | 1.000 |
| worst_case_corner_gameweeks_12 | 12 | 0.093 | 0.281 | 0.555 | 0.957 | 1.000 | 1.000 |
| worst_case_corner_gameweeks_16 | 16 | 0.092 | 0.335 | 0.671 | 0.993 | 1.000 | 1.000 |
| worst_case_corner_gameweeks_24 | 24 | 0.122 | 0.420 | 0.826 | 1.000 | 1.000 | 1.000 |
| worst_case_corner_gameweeks_38 | 38 | 0.147 | 0.621 | 0.963 | 1.000 | 1.000 | 1.000 |
| worst_case_corner_managers_500 | 5 | invalid | invalid | invalid | invalid | invalid | invalid |
| worst_case_corner_managers_1000 | 5 | invalid | invalid | invalid | invalid | invalid | invalid |

Null share for the false-alarm check: 50%; studies per cell: 1,000 pre-registered.
