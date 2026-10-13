"""Section 1.1 - Confirm and record the environment.

What this script does, in order:
  1. Reads the hardware and operating-system facts of this machine.
  2. Connects to the EMQX broker (proves the broker is running) and asks it
     for its version.
  3. Connects to the assignment database (proves PostgreSQL is running),
     and reads the PostgreSQL / TimescaleDB versions, the four configuration
     values the assignment lists, and the session time zone.
  4. Checks that the machine clock is synchronized by asking an internet time
     server, and compares the machine clock with the database clock.
  5. Prints everything as one table and saves it to
     results/1_1_environment.md so it can be pasted into the report.

Run:  python s11_environment.py
"""

from __future__ import annotations

import os
import platform
import socket
import struct
import subprocess
import sys
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import psutil

from common import (RESULTS_DIR, cat_text, connect, finish_log, format_table,
                    load_env, setting, start_log)

STEP = "1_1_environment"


def run_command(command: list[str]) -> str:
    """Run an operating-system command and return its text ('' if it fails)."""
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=20)
        return done.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def cpu_model() -> str:
    """The CPU name is stored in a different place on every operating system."""
    system = platform.system()
    if system == "Windows":
        name = run_command(["powershell", "-NoProfile", "-Command",
                            "(Get-CimInstance Win32_Processor).Name"])
        return name.splitlines()[0].strip() if name else platform.processor()
    if system == "Darwin":
        return run_command(["sysctl", "-n", "machdep.cpu.brand_string"]) or platform.processor()
    try:                                              # Linux
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            for line in handle:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def detected_storage() -> str:
    """Best-effort disk type detection. The value in .env is what gets reported;
    this is only printed as a hint so you can fill STORAGE_TYPE in correctly."""
    system = platform.system()
    if system == "Windows":
        return run_command(["powershell", "-NoProfile", "-Command",
                            "Get-PhysicalDisk | ForEach-Object { $_.FriendlyName + ' / ' + "
                            "$_.MediaType + ' / ' + $_.BusType }"]).replace("\n", "; ")
    if system == "Linux":
        return run_command(["lsblk", "-d", "-n", "-o", "NAME,ROTA,TRAN,MODEL"]).replace("\n", "; ")
    return ""


def emqx_version(env: dict) -> tuple[bool, str]:
    """Connect to the broker and read its version from the $SYS system topic.

    EMQX publishes its version on $SYS/brokers/<node>/version as a retained
    message. Clients on localhost are allowed to read $SYS topics by default.
    Returns (broker_reachable, version_text).
    """
    found: dict = {"connected": False, "version": ""}

    def on_connect(client, userdata, flags, reason_code, properties):
        found["connected"] = not reason_code.is_failure
        client.subscribe("$SYS/brokers/+/version", qos=0)

    def on_message(client, userdata, message):
        found["version"] = message.payload.decode("utf-8", "replace")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="env-check")
    if env["MQTT_USERNAME"]:
        client.username_pw_set(env["MQTT_USERNAME"], env["MQTT_PASSWORD"])
    client.on_connect, client.on_message = on_connect, on_message
    try:
        client.connect(env["MQTT_HOST"], int(env["MQTT_PORT"]), keepalive=30)
    except OSError as exc:
        return False, f"NOT REACHABLE ({exc})"
    client.loop_start()
    deadline = time.time() + 4                       # wait up to 4 s for the answer
    while time.time() < deadline and not found["version"]:
        time.sleep(0.1)
    client.loop_stop()
    client.disconnect()
    version = found["version"] or os.environ.get("EMQX_VERSION", "")
    return found["connected"], version or "connected, version not readable - set EMQX_VERSION in .env"


def ntp_offset_ms(server: str = "pool.ntp.org") -> float | None:
    """Ask an internet time server how far off this machine's clock is.

    This is a minimal SNTP request (RFC 4330): send 48 bytes, read 48 bytes,
    and take the server's transmit timestamp from bytes 40-47.
    Returns the offset in milliseconds, or None when there is no internet.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(4)
            sent = time.time()
            sock.sendto(b"\x1b" + 47 * b"\0", (server, 123))
            data, _ = sock.recvfrom(48)
            received = time.time()
        seconds, fraction = struct.unpack("!II", data[40:48])
        server_time = seconds - 2208988800 + fraction / 2**32   # 1900 -> 1970 epoch
        return (server_time - (sent + received) / 2) * 1000
    except OSError:
        return None


def main() -> None:
    start_log(STEP)
    env = load_env()
    rows: list[tuple[str, str]] = []

    # ---- 1. Machine ----------------------------------------------------------
    memory = psutil.virtual_memory()
    rows += [
        ("Machine identifier", setting("MACHINE_ID")),
        ("CPU model", cpu_model()),
        ("CPU cores", f"{psutil.cpu_count(logical=False)} physical / {psutil.cpu_count(logical=True)} logical"),
        ("RAM", f"{memory.total / 1024**3:.1f} GB"),
        ("Operating system", f"{platform.system()} {platform.release()} (version {platform.version()})"),
        ("Storage type", os.environ.get("STORAGE_TYPE", "<set STORAGE_TYPE in .env>")),
        ("Python", sys.version.split()[0]),
    ]
    hint = detected_storage()
    if hint:
        print(f"Detected disks (hint for STORAGE_TYPE in .env): {hint}")

    # ---- 2. EMQX broker ------------------------------------------------------
    reachable, version = emqx_version(env)
    rows += [
        ("EMQX broker", f"{'RUNNING' if reachable else 'DOWN'} at {env['MQTT_HOST']}:{env['MQTT_PORT']}"),
        ("EMQX version", version),
    ]

    # ---- 3. PostgreSQL and TimescaleDB --------------------------------------
    conn = connect()
    one = lambda sql: conn.execute(sql).fetchone()[0]     # helper: single value
    rows += [
        ("Database connection", f"database '{one('SELECT current_database()')}' as user "
                                f"'{one('SELECT current_user')}' on {env['PGHOST']}:{env['PGPORT']}"),
        ("PostgreSQL version", one("SHOW server_version")),
        ("TimescaleDB version", one("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")),
        ("PostgreSQL runs", os.environ.get("PG_RUNTIME", "<set PG_RUNTIME in .env>")),
        ("shared_buffers", one("SHOW shared_buffers")),
        ("work_mem", one("SHOW work_mem")),
        ("max_parallel_workers_per_gather", one("SHOW max_parallel_workers_per_gather")),
        ("jit", one("SHOW jit")),
        ("Session time zone", one("SHOW TimeZone")),
    ]

    # ---- 4. Clock ------------------------------------------------------------
    database_clock = one("SELECT clock_timestamp()")
    machine_clock = datetime.now(timezone.utc)
    offset = ntp_offset_ms()
    rows += [
        ("Machine clock (CAT)", cat_text(machine_clock)),
        ("Database clock (CAT)", cat_text(database_clock)),
        ("Database minus machine clock", f"{(database_clock - machine_clock).total_seconds() * 1000:+.1f} ms"),
        ("Offset from internet time (NTP)",
         f"{offset:+.1f} ms (synchronized)" if offset is not None and abs(offset) < 1000
         else (f"{offset:+.1f} ms - RESYNC THE CLOCK" if offset is not None
               else "NTP not reachable - show the OS time-sync status instead")),
        ("Recorded at", cat_text()),
    ]
    conn.close()

    # ---- 5. Print and save ---------------------------------------------------
    print()
    print(format_table(["Item", "Value"], rows))
    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 1.1 Environment record\n\n" + format_table(["Item", "Value"], rows, markdown=True) + "\n",
        encoding="utf-8")
    print(f"\nSaved to results/{STEP}.md")
    finish_log(STEP)


if __name__ == "__main__":
    main()
