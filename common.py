"""Shared helpers used by every step script in this project.

Nothing in here is specific to one assignment section. It only removes
repetition so that the step scripts (s11_..., s12_..., ...) stay short and
readable:

  * load_env()            read connection settings from the .env file
  * connect()             open a PostgreSQL connection with the CAT session zone
  * now_cat(), cat_text() wall-clock helpers, always in CAT (UTC+02:00)
  * print_table()         print a list of rows as an aligned text table
  * show_query()          print a SQL statement, run it, print its result
  * load_named_queries()  read "-- name: xxx" blocks out of a .sql file
  * start_log()           copy everything printed on screen into results/
  * file_logger()         detailed fault log in logs/ with CAT timestamps

Only the Python standard library and psycopg (the PostgreSQL driver) are used.
"""

from __future__ import annotations

import logging
import os
import re
import socket
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

# --------------------------------------------------------------------------
# Paths. Everything is resolved relative to this file so the scripts work no
# matter which folder the terminal is in.
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
SQL_DIR = ROOT / "sql"
RESULTS_DIR = ROOT / "results"
LOGS_DIR = ROOT / "logs"
DATA_DIR = ROOT / "data"          # large intermediate CSV files (git-ignored)
for _folder in (RESULTS_DIR, LOGS_DIR, DATA_DIR):
    _folder.mkdir(exist_ok=True)

# --------------------------------------------------------------------------
# Time. The assignment requires every recorded time to be in CAT. Rwanda does
# not use daylight saving time, so CAT is always exactly UTC+02:00.
# --------------------------------------------------------------------------
CAT = timezone(timedelta(hours=2), "CAT")
DB_TIMEZONE = "Africa/Kigali"     # the PostgreSQL name for the same zone

# Fixed facts about the common dataset (see dataset_info() in the generator).
PERIOD_START = "2026-09-01 00:00:00+02"   # inclusive
PERIOD_END = "2026-09-29 00:00:00+02"     # exclusive
READINGS_PER_DAY = 96                     # one reading every 15 minutes


def now_cat() -> datetime:
    """Current wall-clock time expressed in CAT."""
    return datetime.now(CAT)


def cat_text(value: datetime | None = None) -> str:
    """Format a datetime as 'YYYY-MM-DD HH:MM:SS.mmm CAT' for logs and reports."""
    value = (value or now_cat()).astimezone(CAT)
    return value.strftime("%Y-%m-%d %H:%M:%S.") + f"{value.microsecond // 1000:03d} CAT"


# --------------------------------------------------------------------------
# Settings. Secrets are never written in the code. They live in a local file
# named .env (copied from .env.example) which is excluded from Git.
# --------------------------------------------------------------------------
_DEFAULTS = {
    "PGHOST": "localhost",
    "PGPORT": "5432",
    "PGUSER": "postgres",
    "PGPASSWORD": "",
    "PGDATABASE": "energy_grid",
    "MQTT_HOST": "localhost",
    "MQTT_PORT": "1883",
    "MQTT_USERNAME": "",
    "MQTT_PASSWORD": "",
    "MACHINE_ID": socket.gethostname(),
}
_env_loaded = False


def load_env() -> dict:
    """Read KEY=VALUE lines from .env into os.environ (existing values win)."""
    global _env_loaded
    env_file = ROOT / ".env"
    if not _env_loaded and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    _env_loaded = True
    return {key: os.environ.get(key, default) for key, default in _DEFAULTS.items()}


def setting(name: str) -> str:
    """Return one setting, falling back to the default above."""
    return load_env()[name]


def connect(dbname: str | None = None, autocommit: bool = True) -> psycopg.Connection:
    """Open a PostgreSQL connection.

    autocommit=True means every statement is committed as soon as it finishes.
    That is what we want for DDL, for TimescaleDB procedures such as
    refresh_continuous_aggregate (which refuse to run inside a transaction),
    and for benchmarks. Scripts that need one big transaction pass False.

    The session time zone is forced to Africa/Kigali so that timestamps are
    displayed in CAT and date arithmetic follows CAT days, even if the database
    default was not set.
    """
    env = load_env()
    return psycopg.connect(
        host=env["PGHOST"],
        port=env["PGPORT"],
        user=env["PGUSER"],
        password=env["PGPASSWORD"] or None,
        dbname=dbname or env["PGDATABASE"],
        autocommit=autocommit,
        options=f"-c timezone={DB_TIMEZONE}",
        application_name="energy_grid_assignment",
    )


# --------------------------------------------------------------------------
# Output helpers.
# --------------------------------------------------------------------------
def _cell(value) -> str:
    """Turn one database value into display text."""
    if value is None:
        return "NULL"
    if isinstance(value, float):
        return f"{value:,.6f}".rstrip("0").rstrip(".") if abs(value) < 1e15 else repr(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value:,}" if abs(value) < 1_000_000_000 else str(value)  # keep meter IDs plain
    if isinstance(value, datetime):
        return value.astimezone(CAT).strftime("%Y-%m-%d %H:%M:%S%z") if value.tzinfo else str(value)
    return str(value)


def format_table(headers, rows, markdown: bool = False) -> str:
    """Return rows as an aligned text table (or a Markdown table)."""
    text_rows = [[_cell(v) for v in row] for row in rows]
    headers = [str(h) for h in headers]
    widths = [len(h) for h in headers]
    for row in text_rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(value))
    if markdown:
        lines = ["| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |",
                 "| " + " | ".join("-" * w for w in widths) + " |"]
        lines += ["| " + " | ".join(v.ljust(w) for v, w in zip(row, widths)) + " |" for row in text_rows]
        return "\n".join(lines)
    lines = [" | ".join(h.ljust(w) for h, w in zip(headers, widths)),
             "-+-".join("-" * w for w in widths)]
    lines += [" | ".join(v.ljust(w) for v, w in zip(row, widths)) for row in text_rows]
    lines.append(f"({len(text_rows)} row{'s' if len(text_rows) != 1 else ''})")
    return "\n".join(lines)


def print_table(headers, rows) -> None:
    print(format_table(headers, rows))


def show_query(conn, sql: str, params=None, title: str | None = None, max_rows: int = 50):
    """Print a statement, execute it, and print what came back.

    Printing the SQL next to its result is what makes a terminal screenshot
    acceptable evidence: the marker can see the executed command and its output.
    Returns (headers, rows) so the caller can reuse the values.
    """
    if title:
        print(f"\n--- {title} ---")
    print(sql.strip())
    started = time.perf_counter()
    cur = conn.execute(sql, params)
    headers, rows = [], []
    if cur.description:                       # the statement returned a result set
        headers = [col.name for col in cur.description]
        rows = cur.fetchall()
        elapsed = time.perf_counter() - started
        print()
        print(format_table(headers, rows[:max_rows]))
        if len(rows) > max_rows:
            print(f"... {len(rows) - max_rows} more rows not shown")
    else:                                     # INSERT / UPDATE / DELETE / DDL
        elapsed = time.perf_counter() - started
        print(f"\n{cur.statusmessage}")
    print(f"Time: {elapsed * 1000:,.1f} ms")
    return headers, rows


def load_named_queries(filename: str) -> dict[str, str]:
    """Read a .sql file split into blocks that start with '-- name: something'.

    Keeping the SQL in .sql files (instead of hiding it inside Python strings)
    means the exact text that was benchmarked or shown on a dashboard is the
    text submitted in the repository.
    """
    text = (SQL_DIR / filename).read_text(encoding="utf-8")
    queries: dict[str, str] = {}
    name = None
    for block in re.split(r"^-- name:\s*", text, flags=re.MULTILINE):
        if name is None:            # text before the first marker is a file header
            name = ""
            continue
        first_line, _, body = block.partition("\n")
        queries[first_line.strip()] = body.strip().rstrip(";").strip()
    return queries


class _Tee:
    """Write to the screen and to a file at the same time."""

    def __init__(self, stream, handle):
        self.stream, self.handle = stream, handle

    def write(self, data):
        self.stream.write(data)
        self.handle.write(data)
        return len(data)

    def flush(self):
        self.stream.flush()
        self.handle.flush()


def start_log(step: str) -> Path:
    """Start copying everything this script prints into results/<step>.log.

    The log is the 'recorded' evidence required by section 9.2 and makes it
    easy to copy exact numbers into the report after taking the screenshot.
    A header line records when and where the step was executed.
    """
    try:                                    # Windows consoles default to cp1252
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    path = RESULTS_DIR / f"{step}.log"
    handle = open(path, "w", encoding="utf-8")
    sys.stdout = _Tee(sys.stdout, handle)
    print("=" * 78)
    print(f"{step}   started {cat_text()}   machine {setting('MACHINE_ID')}")
    print("=" * 78)
    return path


def file_logger(name: str) -> logging.Logger:
    """Return a logger that writes logs/<name>.log with CAT timestamps.

    The MQTT programs use it to record every fault (parse error, redelivery,
    failed insert) so that a difference between pilot counts can be explained.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(LOGS_DIR / f"{name}.log", mode="w", encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s CAT %(levelname)s %(message)s")
        formatter.converter = lambda *_: now_cat().timetuple()   # stamp in CAT, not machine zone
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def finish_log(step: str) -> None:
    print("-" * 78)
    print(f"{step}   finished {cat_text()}   (output saved in results/{step}.log)")
