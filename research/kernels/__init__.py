"""Domain-agnostic statistical kernels.

No FPL-specific constants, no governance imports, no signal classification strings.
Anything that imports from signals/ or references FPL concepts belongs in
research/families/, not here.
"""

from research.kernels.correlation.panel import decompose_rho
from research.kernels.correlation.tail import haul_concentration

__all__ = ["decompose_rho", "haul_concentration"]
