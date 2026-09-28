"""Launch a fresh Blender GUI process with its own Blender MCP bridge port."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from typing import Iterator


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = Path(__file__).with_name("blender_mcp_bootstrap.py")
DEFAULT_PORT_RANGE = range(9876, 9976)
LOCK_PATH = Path(tempfile.gettempdir()) / "gk-assets-blender-mcp-launch.lock"


def parse_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def parse_positive_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be a positive number of seconds") from exc
    if not 0 < seconds < float("inf"):
        raise argparse.ArgumentTypeError("timeout must be finite and greater than zero")
    return seconds


@contextmanager
def serialized_launch() -> Iterator[None]:
    """Prevent two launcher invocations from reserving the same free port."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+b") as lock_file:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            while True:
                try:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def reserve_port(requested: int | None) -> tuple[int, socket.socket]:
    """Bind a temporary reservation socket until Blender has been spawned."""
    candidates = (requested,) if requested is not None else DEFAULT_PORT_RANGE
    for port in candidates:
        reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            reservation.bind(("127.0.0.1", port))
        except OSError:
            reservation.close()
            continue
        return port, reservation
    if requested is not None:
        raise OSError(f"port {requested} is already in use")
    raise OSError("no free Blender MCP port in 9876–9975")


def resolve_blender(override: Path | None) -> Path:
    if override is not None:
        executable = override.expanduser().resolve()
    else:
        sys.path.insert(0, str(ROOT / "tools"))
        from blender_path import blender_exe

        executable = Path(blender_exe(prefer_mcp=True)).resolve()
    if not executable.is_file():
        raise FileNotFoundError(f"Blender executable not found: {executable}")
    return executable


def wait_for_bootstrap(process: subprocess.Popen[bytes], log_path: Path, port: int, timeout: float) -> str:
    ready_marker = f"GK_ASSETS_MCP_READY 127.0.0.1 {port} {process.pid}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return "process_exited"
        try:
            log = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            log = ""
        if ready_marker in log:
            return "ready"
        if "GK_ASSETS_MCP_ERROR " in log:
            return "bootstrap_error"
        time.sleep(0.2)
    return "timeout"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Open a new Blender GUI process and start its MCP bridge on an isolated port."
    )
    parser.add_argument("--blend", type=Path, help="optional .blend file to open in the new process")
    parser.add_argument("--blender", type=Path, help="Blender executable (default: tools/blender_path.py resolver)")
    parser.add_argument("--port", type=parse_port, help="request a specific free port; otherwise choose 9876–9975")
    parser.add_argument(
        "--startup-timeout",
        type=parse_positive_seconds,
        default=90.0,
        help="seconds to wait for the bridge bootstrap (default: 90)",
    )
    args = parser.parse_args(argv)

    blend_file = args.blend.expanduser().resolve() if args.blend else None
    if blend_file is not None and not blend_file.is_file():
        parser.error(f".blend file not found: {blend_file}")
    if not BOOTSTRAP.is_file():
        parser.error(f"bootstrap script not found: {BOOTSTRAP}")

    try:
        blender = resolve_blender(args.blender)
    except (FileNotFoundError, OSError) as exc:
        parser.error(str(exc))

    log_dir = Path(tempfile.gettempdir()) / "gk-assets-blender-mcp"
    log_dir.mkdir(parents=True, exist_ok=True)

    with serialized_launch():
        try:
            port, reservation = reserve_port(args.port)
        except OSError as exc:
            parser.error(str(exc))

        log_path = log_dir / f"blender-mcp-{port}-{time.time_ns()}.log"
        cancel_path = log_path.with_suffix(".cancel")
        command = [str(blender)]
        if blend_file is not None:
            command.append(str(blend_file))
        command.extend(("--python", str(BOOTSTRAP)))

        child_env = os.environ.copy()
        child_env["GK_ASSETS_MCP_HOST"] = "127.0.0.1"
        child_env["GK_ASSETS_MCP_PORT"] = str(port)
        child_env["GK_ASSETS_MCP_CANCEL_FILE"] = str(cancel_path)

        try:
            with log_path.open("ab") as log_file:
                popen_options: dict[str, object] = {
                    "cwd": str(ROOT),
                    "env": child_env,
                    "stdin": subprocess.DEVNULL,
                    "stdout": log_file,
                    "stderr": subprocess.STDOUT,
                    "close_fds": True,
                }
                if os.name == "nt":
                    popen_options["creationflags"] = (
                        subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                    )
                else:
                    popen_options["start_new_session"] = True
                process = subprocess.Popen(command, **popen_options)  # type: ignore[arg-type]
        except OSError as exc:
            reservation.close()
            print(json.dumps({"status": "launch_error", "error": str(exc)}, indent=2))
            return 1
        finally:
            # The in-Blender bootstrap retries briefly while this reservation
            # closes, protecting concurrent launcher processes from port reuse.
            reservation.close()

        try:
            status = wait_for_bootstrap(process, log_path, port, args.startup_timeout)
        except KeyboardInterrupt:
            if process.poll() is None:
                cancel_path.write_text("cancel startup", encoding="utf-8")
            raise
        if status == "timeout" and process.poll() is None:
            cancel_path.write_text("cancel startup", encoding="utf-8")

    result: dict[str, object] = {
        "status": status,
        "pid": process.pid,
        "port": port,
        "host": "127.0.0.1",
        "blender": str(blender),
        "blend": str(blend_file) if blend_file is not None else None,
        "log": str(log_path),
    }
    if process.poll() is not None:
        result["exit_code"] = process.returncode
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if status == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
