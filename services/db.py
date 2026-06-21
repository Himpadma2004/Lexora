"""
services/db.py
Lightweight JSON file storage for Lexora session history.
No external database needed — results are saved locally in data/history/.
"""

import json
from datetime import datetime
from pathlib import Path

HISTORY_DIR = Path("data/history")
MAX_RECORDS = 50  # keep the latest N records per module


def _file(module: str) -> Path:
    """Return the path to a module's history file."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return HISTORY_DIR / f"{module}.json"


def save_result(module: str, data: dict) -> None:
    """Append a result to a module's history (with timestamp)."""
    history = load_history(module)
    entry = {"timestamp": datetime.now().isoformat(), **data}
    history.append(entry)
    history = history[-MAX_RECORDS:]  # trim old records
    _file(module).write_text(json.dumps(history, indent=2, ensure_ascii=False))


def load_history(module: str) -> list:
    """Load all saved results for a module. Returns [] if none exist."""
    f = _file(module)
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def clear_history(module: str) -> None:
    """Delete the history file for a module."""
    f = _file(module)
    if f.exists():
        f.unlink()
