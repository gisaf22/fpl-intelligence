"""FPL signal composition rules — algebraic identities between mart fields.

These are definitional rules from the FPL API, not empirical findings.
They hold in every season by construction.

Consequence for analysis: including a composite and its components together
double-counts the same underlying information. Choose one representation
per analysis (composite or components).
"""

# xgi = xg + xa by FPL definition.
# Expected goal involvements is the sum of expected goals (xg) and expected
# assists (xa). All three fields are present in the mart.
XGI_COMPONENTS: tuple[str, ...] = ("xg", "xa")

# ict_index is a composite of influence, creativity, and threat — aggregated
# by FPL's internal formula (not a simple sum; the exact weighting is
# unpublished). All four fields are present in the mart.
ICT_COMPONENTS: tuple[str, ...] = ("influence", "creativity", "threat")

# Canonical composites: the recommended single representative when components
# and composite are both available. Prefer the composite when you want a single
# summary; prefer the components when you need separable contributions.
COMPOSITE_SIGNALS: dict[str, tuple[str, ...]] = {
    "xgi": XGI_COMPONENTS,
    "ict_index": ICT_COMPONENTS,
}
