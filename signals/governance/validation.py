"""Re-export shim — validation rules moved to ``domain.registry.validation``.

Kept so existing ``signals.governance.validation`` importers stay green during
the signals decomposition migration. Removed in PR-7 once all importers repoint.
"""

from __future__ import annotations

from domain.registry.validation import *  # noqa: F403
