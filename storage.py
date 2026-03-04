import json
from pathlib import Path

DATA_DIR = Path("data")
CONFIG_FILE = DATA_DIR / "config.json"
INTERVIEWS_DIR = DATA_DIR / "interviews"


def init_storage():
    """Ensure data directories exist on startup."""
    DATA_DIR.mkdir(exist_ok=True)
    INTERVIEWS_DIR.mkdir(exist_ok=True)


def read_json(filepath: Path) -> dict | None:
    try:
        data = json.loads(filepath.read_text())
        return data if isinstance(data, dict) else None
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_json(filepath: Path, data: dict | list) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")
