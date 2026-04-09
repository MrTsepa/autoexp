"""SQLite experiment store for autoexp."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    commit_sha TEXT NOT NULL,
    hypothesis TEXT,
    status TEXT DEFAULT 'created',
    started_at TEXT,
    finished_at TEXT,
    abort_reason TEXT,
    train_command TEXT,
    eval_command TEXT
);

CREATE TABLE IF NOT EXISTS metrics (
    experiment_id TEXT REFERENCES experiments(id),
    metric_name TEXT,
    value REAL,
    source TEXT,
    recorded_at TEXT,
    PRIMARY KEY (experiment_id, metric_name, recorded_at)
);

CREATE TABLE IF NOT EXISTS evaluations (
    experiment_id TEXT REFERENCES experiments(id),
    eval_name TEXT,
    score REAL,
    raw_output TEXT,
    evaluated_at TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict:
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def init_db(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = _row_to_dict
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def next_experiment_id(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT COUNT(*) as n FROM experiments").fetchone()
    return f"auto_{row['n'] + 1:03d}"


def create_experiment(
    conn: sqlite3.Connection,
    exp_id: str,
    commit_sha: str,
    hypothesis: str,
) -> None:
    conn.execute(
        "INSERT INTO experiments (id, commit_sha, hypothesis, status, started_at) VALUES (?, ?, ?, 'created', ?)",
        (exp_id, commit_sha, hypothesis, _now()),
    )
    conn.commit()


def update_experiment(conn: sqlite3.Connection, exp_id: str, **kwargs) -> None:
    allowed = {"status", "finished_at", "abort_reason", "train_command", "eval_command"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE experiments SET {set_clause} WHERE id = ?",
        [*updates.values(), exp_id],
    )
    conn.commit()


def record_metric(
    conn: sqlite3.Connection,
    experiment_id: str,
    name: str,
    value: float,
    source: str = "train",
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO metrics (experiment_id, metric_name, value, source, recorded_at) VALUES (?, ?, ?, ?, ?)",
        (experiment_id, name, value, source, _now()),
    )
    conn.commit()


def record_eval(
    conn: sqlite3.Connection,
    experiment_id: str,
    eval_name: str,
    score: float,
    raw_output: str = "",
) -> None:
    conn.execute(
        "INSERT INTO evaluations (experiment_id, eval_name, score, raw_output, evaluated_at) VALUES (?, ?, ?, ?, ?)",
        (experiment_id, eval_name, score, raw_output, _now()),
    )
    conn.commit()


def get_experiments(
    conn: sqlite3.Connection,
    last_n: int | None = None,
    status: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM experiments"
    params: list = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY started_at DESC"
    if last_n:
        query += " LIMIT ?"
        params.append(last_n)
    return conn.execute(query, params).fetchall()


def get_experiment(conn: sqlite3.Connection, exp_id: str) -> dict | None:
    return conn.execute("SELECT * FROM experiments WHERE id = ?", (exp_id,)).fetchone()


def get_best(conn: sqlite3.Connection, metric_name: str) -> dict | None:
    row = conn.execute(
        """SELECT e.*, m.value as best_value
           FROM experiments e
           JOIN metrics m ON e.id = m.experiment_id
           WHERE m.metric_name = ? AND e.status = 'completed'
           ORDER BY m.value DESC LIMIT 1""",
        (metric_name,),
    ).fetchone()
    return row


def get_evals(conn: sqlite3.Connection, experiment_id: str) -> list[dict]:
    return conn.execute(
        "SELECT * FROM evaluations WHERE experiment_id = ? ORDER BY evaluated_at",
        (experiment_id,),
    ).fetchall()


def get_metrics(conn: sqlite3.Connection, experiment_id: str) -> list[dict]:
    return conn.execute(
        "SELECT * FROM metrics WHERE experiment_id = ? ORDER BY recorded_at",
        (experiment_id,),
    ).fetchall()
