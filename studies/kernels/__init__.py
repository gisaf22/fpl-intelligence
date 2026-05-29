"""Domain-agnostic statistical kernels.

No FPL-specific constants, no governance imports, no signal classification strings.
Anything that imports from signals/ or references FPL concepts belongs in studies/lenses/,
not here.
"""

from studies.kernels.correlation.panel import decompose_rho
from studies.kernels.correlation.tail import haul_concentration
