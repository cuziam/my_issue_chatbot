#!/usr/bin/env python3
"""Server launcher with automatic cleanup of stale processes.

Ensures only one uvicorn instance runs on the configured port.
Tracks PID via a pidfile so restarts are always clean.
Detects zombie sockets on Windows and auto-switches to a free port.
Automatically updates vite.config.ts proxy target to match.

Usage:
    python web/run_server.py              # start (foreground, auto-reload)
    python web/run_server.py --stop       # stop running server
    python web/run_server.py --restart    # stop + start
    python web/run_server.py --status     # check if running
    python web/run_server.py --port 8001  # override port
"""
from __future__ import annotations

import argparse
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.absolute()
PID_FILE = ROOT_DIR / "logs" / "server.pid"
PORT_FILE = ROOT_DIR / "logs" / "server.port"
VITE_CONFIG = ROOT_DIR / "web" / "frontend" / "vite.config.ts"
DEFAULT_PORT = 8000
PORT_RANGE = (8000, 8010)  # auto-scan range
DEFAULT_HOST = "0.0.0.0"


# ---------------------------------------------------------------------------
# PID / port file helpers
# ---------------------------------------------------------------------------

def _read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        return pid if pid > 0 else None
    except (ValueError, OSError):
        return None


def _read_port() -> int | None:
    if not PORT_FILE.exists():
        return None
    try:
        return int(PORT_FILE.read_text().strip())
    except (ValueError, OSError):
        return None


def _write_pid(pid: int) -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(pid))


def _write_port(port: int) -> None:
    PORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    PORT_FILE.write_text(str(port))


def _remove_pid() -> None:
    PID_FILE.unlink(missing_ok=True)


def _remove_port() -> None:
    PORT_FILE.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------

def _is_process_alive(pid: int) -> bool:
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in result.stdout
        except (subprocess.SubprocessError, OSError):
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _kill_process(pid: int, timeout: float = 5.0) -> bool:
    if not _is_process_alive(pid):
        return True

    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                capture_output=True, timeout=10,
            )
        except (subprocess.SubprocessError, OSError):
            pass
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _is_process_alive(pid):
            return True
        time.sleep(0.3)

    # Force kill
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                capture_output=True, timeout=10,
            )
        except (subprocess.SubprocessError, OSError):
            pass
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    time.sleep(0.5)
    return not _is_process_alive(pid)


def _find_pids_on_port(port: int) -> list[int]:
    pids: set[int] = set()
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    try:
                        pid = int(parts[-1])
                        if pid > 0:
                            pids.add(pid)
                    except ValueError:
                        pass
    except (subprocess.SubprocessError, OSError):
        pass
    return list(pids)


# ---------------------------------------------------------------------------
# Port management — detect zombie sockets and find a clean port
# ---------------------------------------------------------------------------

def _is_port_truly_free(port: int) -> bool:
    """Check if a port is free — no zombie sockets, no live server.

    On Windows, zombie sockets can linger after process death.  Even with
    SO_REUSEADDR a new server can bind alongside a zombie, but incoming
    requests may be routed to the zombie → stale responses.

    We check by trying to connect: if something answers, the port is NOT free.
    Then we verify whether the responder is a live process or a zombie.
    """
    # First: can anything accept a connection on this port?
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            # Something is listening — port is NOT free
            # Check if it's a zombie
            pids = _find_pids_on_port(port)
            has_live = any(_is_process_alive(p) for p in pids)
            if not has_live and pids:
                # Only zombies — port is occupied by zombie sockets
                return False
            # Live process on port
            return False
    except (ConnectionRefusedError, OSError, TimeoutError):
        # Nothing accepting connections — port is free
        return True


def _has_zombie_sockets(port: int) -> bool:
    """Check if a port has zombie sockets (netstat shows LISTENING but no live process)."""
    pids = _find_pids_on_port(port)
    if not pids:
        return False
    # If any PID is NOT a real process, that's a zombie socket
    for pid in pids:
        if not _is_process_alive(pid):
            return True
    return False


def _find_free_port(preferred: int) -> int:
    """Find a free port, starting from preferred. Auto-scans PORT_RANGE."""
    # Try preferred first
    if _is_port_truly_free(preferred):
        return preferred

    # Scan range
    for port in range(PORT_RANGE[0], PORT_RANGE[1] + 1):
        if port != preferred and _is_port_truly_free(port):
            return port

    raise RuntimeError(f"No free port found in range {PORT_RANGE[0]}-{PORT_RANGE[1]}")


# ---------------------------------------------------------------------------
# Vite config sync
# ---------------------------------------------------------------------------

def _update_vite_proxy(port: int) -> bool:
    """Update vite.config.ts proxy target to point to the given port.

    Returns True if the file was modified.
    """
    if not VITE_CONFIG.exists():
        return False

    content = VITE_CONFIG.read_text(encoding="utf-8")
    # Match: target: 'http://localhost:NNNN'
    pattern = r"(target:\s*['\"])http://localhost:\d+(['\"])"
    replacement = rf"\g<1>http://localhost:{port}\g<2>"

    new_content = re.sub(pattern, replacement, content)
    if new_content != content:
        VITE_CONFIG.write_text(new_content, encoding="utf-8")
        return True
    return False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def stop_server(port: int | None = None) -> bool:
    """Stop the running server. Tries PID file first, then port scan."""
    if port is None:
        port = _read_port() or DEFAULT_PORT

    stopped = False

    # 1. Try PID file
    pid = _read_pid()
    if pid and _is_process_alive(pid):
        print(f"Stopping server (PID {pid}) from pidfile...")
        if _kill_process(pid):
            print(f"  Stopped PID {pid}")
            stopped = True

    # 2. Scan port for any remaining live processes
    for p in _find_pids_on_port(port):
        if _is_process_alive(p):
            print(f"Killing stale process on port {port} (PID {p})...")
            if _kill_process(p):
                print(f"  Stopped PID {p}")
                stopped = True

    _remove_pid()
    _remove_port()

    if stopped:
        for _ in range(10):
            if _is_port_truly_free(port):
                break
            time.sleep(0.5)

    return stopped


def server_status(port: int | None = None) -> None:
    saved_port = _read_port()
    port = port or saved_port or DEFAULT_PORT
    pid = _read_pid()

    if pid and _is_process_alive(pid):
        print(f"Server is RUNNING (PID {pid}, port {port})")
    else:
        port_pids = _find_pids_on_port(port)
        alive = [p for p in port_pids if _is_process_alive(p)]
        if alive:
            print(f"Server is RUNNING (port {port}, PIDs: {alive}) — no pidfile")
        else:
            zombie = _has_zombie_sockets(port)
            print(f"Server is STOPPED (port {port})")
            if zombie:
                print(f"  Warning: Zombie sockets detected on port {port}")
                print(f"  Next start will auto-select a free port")
            if pid:
                print(f"  Stale pidfile found (PID {pid}), cleaning up...")
                _remove_pid()


def start_server(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST) -> None:
    """Start the uvicorn server with --reload.

    Automatically kills existing server, detects zombie sockets,
    and switches to a free port if needed.
    """
    # Stop existing
    pid = _read_pid()
    port_pids = _find_pids_on_port(port)

    if (pid and _is_process_alive(pid)) or any(_is_process_alive(p) for p in port_pids):
        print(f"Existing server detected on port {port}, stopping...")
        stop_server(port)
        time.sleep(1)

    # Find a truly free port (handles zombie sockets)
    actual_port = _find_free_port(port)
    if actual_port != port:
        if _has_zombie_sockets(port):
            print(f"Warning: Zombie sockets on port {port} (dead processes still holding the port)")
            print(f"  This is a Windows OS issue - sockets from crashed processes linger.")
            print(f"  They will eventually be cleaned up by the OS.")
        print(f"Auto-switching to port {actual_port}")
        print()

    # Sync vite proxy
    if _update_vite_proxy(actual_port):
        print(f"Updated vite.config.ts proxy → localhost:{actual_port}")

    # Clean __pycache__ to prevent stale bytecode
    _clean_pycache()

    print(f"Starting server on {host}:{actual_port} with auto-reload...")
    print(f"PID file: {PID_FILE}")
    print()

    cmd = [
        sys.executable, "-m", "uvicorn",
        "web.backend.main:app",
        "--host", host,
        "--port", str(actual_port),
        "--reload",
        "--reload-dir", "web",
    ]

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(ROOT_DIR),
        )
        _write_pid(process.pid)
        _write_port(actual_port)
        print(f"Server started (PID {process.pid}, port {actual_port})")
        print("Press Ctrl+C to stop")
        print()

        process.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        _kill_process(process.pid)
    finally:
        _remove_pid()
        _remove_port()
        # Restore vite config to default port
        if actual_port != DEFAULT_PORT:
            if _update_vite_proxy(DEFAULT_PORT):
                print(f"Restored vite.config.ts proxy → localhost:{DEFAULT_PORT}")


def _clean_pycache() -> None:
    """Remove __pycache__ directories under web/ to prevent stale bytecode."""
    web_dir = ROOT_DIR / "web"
    count = 0
    for cache_dir in web_dir.rglob("__pycache__"):
        if cache_dir.is_dir():
            import shutil
            shutil.rmtree(cache_dir, ignore_errors=True)
            count += 1
    if count:
        print(f"Cleaned {count} __pycache__ directories")


def main():
    parser = argparse.ArgumentParser(description="Server launcher")
    parser.add_argument("--stop", action="store_true", help="Stop the running server")
    parser.add_argument("--restart", action="store_true", help="Restart the server")
    parser.add_argument("--status", action="store_true", help="Check server status")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Preferred port (default: {DEFAULT_PORT})")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host (default: {DEFAULT_HOST})")
    args = parser.parse_args()

    if args.status:
        server_status(args.port)
    elif args.stop:
        if stop_server(args.port):
            print("Server stopped.")
        else:
            print("No running server found.")
    elif args.restart:
        stop_server(args.port)
        time.sleep(1)
        start_server(args.port, args.host)
    else:
        start_server(args.port, args.host)


if __name__ == "__main__":
    main()
