"""Pause, resume or list the assignment's TimescaleDB background jobs.

Background jobs are the policies created in this assignment:
    * compression policies            (Section 4.1)
    * continuous-aggregate refreshes  (Section 6.1)

The benchmark rules (3.2, 4.3, 7.4) say only the workload being measured may
run, so the jobs are paused before timing and resumed afterwards.

    python jobs.py status                 list every assignment job
    python jobs.py pause                  stop the scheduler from starting them
    python jobs.py resume                 let the scheduler run them again
    python jobs.py pause  --kind compression        only compression policies
    python jobs.py resume --kind aggregate          only continuous-aggregate policies

How it works
    TimescaleDB keeps one row per job in timescaledb_information.jobs.
    alter_job(job_id, scheduled => false) keeps the job and its settings but
    stops the scheduler from launching it. scheduled => true undoes that.
    Job IDs below 1000 are TimescaleDB's own internal jobs and are left alone.
"""

from __future__ import annotations

import argparse

from common import connect, finish_log, show_query, start_log

# proc_name values used by TimescaleDB for the two policy types.
KINDS = {
    "compression": ("policy_compression", "policy_columnstore"),
    "aggregate": ("policy_refresh_continuous_aggregate",),
}

STATUS_SQL = """
SELECT j.job_id,
       j.proc_name                AS policy,
       j.hypertable_name          AS on_table,
       j.schedule_interval::text  AS runs_every,
       j.scheduled                AS enabled,
       j.config::text             AS settings,
       s.last_run_status,
       s.total_runs
FROM timescaledb_information.jobs j
LEFT JOIN timescaledb_information.job_stats s USING (job_id)
WHERE j.job_id >= 1000
ORDER BY j.job_id"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Pause, resume or list assignment background jobs.")
    parser.add_argument("action", choices=["status", "pause", "resume"])
    parser.add_argument("--kind", choices=list(KINDS), help="limit to one policy type (default: all)")
    args = parser.parse_args()
    start_log(f"jobs_{args.action}")
    conn = connect()

    if args.action in ("pause", "resume"):
        wanted = KINDS[args.kind] if args.kind else sum(KINDS.values(), ())
        jobs = conn.execute(
            "SELECT job_id, proc_name, hypertable_name FROM timescaledb_information.jobs "
            "WHERE job_id >= 1000 AND proc_name = ANY(%s) ORDER BY job_id", (list(wanted),)).fetchall()
        enable = args.action == "resume"
        for job_id, proc_name, table in jobs:
            # The statement is printed so the screenshot shows what was executed.
            print(f"SELECT alter_job({job_id}, scheduled => {str(enable).lower()});   -- {proc_name} on {table}")
            conn.execute("SELECT alter_job(%s, scheduled => %s)", (job_id, enable))
        print(f"\n{len(jobs)} job(s) {'resumed' if enable else 'paused'}.")

    show_query(conn, STATUS_SQL, title="Background job status (enabled = scheduled)")
    conn.close()
    finish_log(f"jobs_{args.action}")


if __name__ == "__main__":
    main()
