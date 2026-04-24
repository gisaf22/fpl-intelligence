from pathlib import Path

DB_PATH: Path = Path("~/.fpl/fpl.db").expanduser()

# TODO: wrong name, should it be lookback window?
MINUTES_FILTER_LOOKBACK: int = 6
DGW_DIVERGENCE_WEIGHT: float = 1.5
OVR_TOP_N: int = 20
MIN_EVAL_POOL_SIZE: int = 20
