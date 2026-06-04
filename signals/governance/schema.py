"""Re-export shim — the registry contract moved to ``domain.registry.schema``.

Kept so existing ``signals.governance.schema`` importers stay green during the
signals decomposition migration. Removed in PR-7 once all importers repoint.
"""

from __future__ import annotations

from domain.registry.schema import *  # noqa: F403
