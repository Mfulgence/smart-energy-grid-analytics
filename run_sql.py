"""Run a .sql file (or one statement) and print every statement with its result.

Why this exists
    The assignment asks for screenshots that show "the executed command and its
    result". This small runner prints each SQL statement, then the rows or the
    status it produced, then how long it took. It works the same on Windows,
    macOS and Linux and does not need psql on the PATH.

    The .sql files contain plain SQL only (no psql backslash commands), so if
    you prefer psql you can run the very same files with:
        psql -a -d energy_grid -f sql/01_2_create_tables.sql

Usage
    python run_sql.py sql/01_2_create_tables.sql
    python run_sql.py sql/01_1a_create_database.sql --db postgres
    python run_sql.py -c "SELECT count(*) FROM meters"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

from common import connect, finish_log, show_query, start_log


def split_statements(text: str) -> list[str]:
    """Split SQL text on semicolons that are real statement terminators.

    A semicolon does NOT end a statement when it sits inside:
      * a 'single-quoted string'      (two quotes '' are an escaped quote)
      * a "double-quoted identifier"
      * a -- line comment or a /* block comment */
      * a $$ dollar-quoted body $$    (used by DO blocks and functions)
    The scanner below walks through the text once and tracks which of those
    states it is in.
    """
    statements, current = [], []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "-" and nxt == "-":                       # line comment
            end = text.find("\n", i)
            end = n if end == -1 else end
            current.append(text[i:end])
            i = end
        elif ch == "/" and nxt == "*":                     # block comment
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            current.append(text[i:end])
            i = end
        elif ch in ("'", '"'):                             # quoted text
            j = i + 1
            while j < n:
                if text[j] == ch:
                    if j + 1 < n and text[j + 1] == ch:    # doubled quote = escape
                        j += 2
                        continue
                    break
                j += 1
            current.append(text[i:j + 1])
            i = j + 1
        elif ch == "$":                                    # maybe a dollar quote
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            if j < n and text[j] == "$":
                tag = text[i:j + 1]                        # e.g. $$ or $body$
                end = text.find(tag, j + 1)
                end = n if end == -1 else end + len(tag)
                current.append(text[i:end])
                i = end
            else:
                current.append(ch)
                i += 1
        elif ch == ";":                                    # real terminator
            statements.append("".join(current).strip())
            current = []
            i += 1
        else:
            current.append(ch)
            i += 1
    statements.append("".join(current).strip())
    return [s for s in statements if _has_sql(s)]


def _has_sql(statement: str) -> bool:
    """True when a block contains more than comments and blank lines."""
    for line in statement.splitlines():
        line = line.strip()
        if line and not line.startswith("--"):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SQL and print each statement with its result.")
    parser.add_argument("file", nargs="?", help="path to a .sql file")
    parser.add_argument("-c", "--command", help="run this single SQL statement instead of a file")
    parser.add_argument("--db", help="database to connect to (default: PGDATABASE from .env)")
    parser.add_argument("--max-rows", type=int, default=60, help="rows to print per result")
    args = parser.parse_args()
    if not args.file and not args.command:
        parser.error("give a .sql file or -c \"statement\"")

    if args.command:
        step, statements = "sql_command", [args.command.rstrip(";")]
    else:
        path = Path(args.file)
        step = "sql_" + path.stem
        statements = split_statements(path.read_text(encoding="utf-8"))

    start_log(step)
    conn = connect(dbname=args.db)
    # Messages raised by the server (NOTICE, WARNING) are printed too.
    conn.add_notice_handler(lambda diag: print(f"{diag.severity}: {diag.message_primary}"))
    info = conn.info
    print(f"Connected to database '{info.dbname}' as '{info.user}' on {info.host}:{info.port}")

    for number, statement in enumerate(statements, start=1):
        print(f"\n[{number}/{len(statements)}]")
        try:
            show_query(conn, statement, max_rows=args.max_rows)
        except psycopg.errors.DuplicateDatabase as exc:
            # Re-running the "create database" file is harmless: keep going.
            print(f"\nNOTICE: {exc.diag.message_primary} - nothing to do")
        except psycopg.Error as exc:
            print(f"\nERROR: {exc}")
            print("Stopped. Fix the problem above and run the file again.")
            conn.close()
            return 1
    conn.close()
    finish_log(step)
    return 0


if __name__ == "__main__":
    sys.exit(main())
