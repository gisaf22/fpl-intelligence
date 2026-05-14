import os
from pathlib import Path

DB_PATH: Path = Path(os.environ.get("FPL_DB_PATH", "~/.fpl/fpl.db")).expanduser()
