"""Platform-abstraction utilities for cross-platform support.

Centralizes Windows vs. Linux differences so consuming code stays clean.
"""
import os
import signal
import subprocess
import time

IS_WINDOWS = os.name == "nt"


def is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID exists."""
    if IS_WINDOWS:
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


def kill_process(pid: int, timeout: float = 5.0) -> bool:
    """Kill a process gracefully, then forcefully. Returns True if dead."""
    if not is_process_alive(pid):
        return True

    if IS_WINDOWS:
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
        if not is_process_alive(pid):
            return True
        time.sleep(0.3)

    # Force kill
    if IS_WINDOWS:
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
    return not is_process_alive(pid)


def find_pids_on_port(port: int) -> list[int]:
    """Find PIDs listening on a given port."""
    pids: set[int] = set()
    if IS_WINDOWS:
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
    else:
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.strip().splitlines():
                try:
                    pid = int(line.strip())
                    if pid > 0:
                        pids.add(pid)
                except ValueError:
                    pass
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            pass
    return list(pids)


def subprocess_creation_flags() -> int:
    """Return subprocess creation flags appropriate for the platform."""
    if IS_WINDOWS:
        return subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return 0


def tar_extra_flags() -> list[str]:
    """Return extra tar flags needed on Windows (--force-local)."""
    if IS_WINDOWS:
        return ["--force-local"]
    return []


# Windows NTSTATUS exit code interpretation
_WINDOWS_EXIT_CODES: dict[int, str] = {
    0xC000013A: "STATUS_CONTROL_C_EXIT (process terminated by Ctrl+C or cancel)",
    0xC0000005: "STATUS_ACCESS_VIOLATION (crash)",
    0xC00000FD: "STATUS_STACK_OVERFLOW (stack overflow)",
    0xC0000374: "STATUS_HEAP_CORRUPTION (heap corruption)",
}


def interpret_exit_code(exit_code: int) -> str:
    """Convert exit code to human-readable string."""
    if exit_code == 0:
        return "success"
    code = exit_code & 0xFFFFFFFF if exit_code < 0 else exit_code
    if IS_WINDOWS and code in _WINDOWS_EXIT_CODES:
        return _WINDOWS_EXIT_CODES[code]
    if code > 0x80000000:
        return f"Windows error 0x{code:08X}"
    return f"exit code {exit_code}"


def is_retryable_exit(exit_code: int) -> bool:
    """Check if exit code indicates a transient failure worth retrying."""
    code = exit_code & 0xFFFFFFFF if exit_code < 0 else exit_code
    return code in {0xC000013A}  # STATUS_CONTROL_C_EXIT
