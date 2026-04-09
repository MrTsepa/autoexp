"""Load .autoexp/config.yaml."""

from pathlib import Path

import yaml

AUTOEXP_DIR = ".autoexp"
CONFIG_FILE = "config.yaml"
DB_FILE = "experiments.db"
PROGRAM_FILE = "program.md"


def get_autoexp_dir() -> Path:
    return Path(AUTOEXP_DIR)


def load_config(path: str | Path | None = None) -> dict:
    if path is None:
        path = get_autoexp_dir() / CONFIG_FILE
    path = Path(path)
    if not path.exists():
        return {
            "editable_files": ["*"],
            "locked_files": [],
            "abort_rules": [],
        }
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    cfg.setdefault("editable_files", ["*"])
    cfg.setdefault("locked_files", [])
    cfg.setdefault("abort_rules", [])
    return cfg
