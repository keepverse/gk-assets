"""Send Python code directly to one or more running Blender MCP add-on ports.

This speaks the add-on's null-delimited TCP request protocol, without starting
the MCP stdio server. Each request runs in the target Blender process.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import socket
import sys


MAX_REQUEST_BYTES = 10 * 1024 * 1024  # Matches blender_mcp_addon's 10 MiB guard.
MAX_RESPONSE_BYTES = 64 * 1024 * 1024  # Bound memory if a target returns unexpected data.
RECV_BUFFER_SIZE = 65536
MAX_PARALLEL_TARGETS = 32


def parse_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def parse_timeout(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be a positive number of seconds") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("timeout must be greater than zero")
    return timeout


def make_request(code: str) -> bytes:
    # The add-on protocol is compact JSON terminated by one NUL byte. Keep
    # strict_json false to match execute_blender_code: Blender IDs in `result`
    # are represented with repr instead of making an otherwise useful response fail.
    body = json.dumps(
        {"type": "execute", "code": code, "strict_json": False},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    request = body + b"\0"
    if len(request) > MAX_REQUEST_BYTES:
        raise ValueError("request exceeds the add-on's 10 MiB limit")
    return request


def execute_at(host: str, port: int, request: bytes, timeout: float) -> dict[str, object]:
    target = f"{host}:{port}"
    try:
        with socket.create_connection((host, port), timeout=timeout) as connection:
            connection.settimeout(timeout)
            connection.sendall(request)
            response = bytearray()
            while True:
                chunk = connection.recv(RECV_BUFFER_SIZE)
                if not chunk:
                    raise ConnectionError("Blender closed the socket before sending a complete response")
                response.extend(chunk)
                delimiter = response.find(b"\0")
                if delimiter >= 0:
                    if delimiter > MAX_RESPONSE_BYTES:
                        raise ConnectionError("response exceeds the CLI's 64 MiB limit")
                    payload = bytes(response[:delimiter])
                    break
                if len(response) > MAX_RESPONSE_BYTES:
                    raise ConnectionError("response exceeds the CLI's 64 MiB limit")

        decoded = json.loads(payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ConnectionError("Blender returned JSON that was not an object")
        return {"target": target, "response": decoded}
    except socket.timeout:
        return {"target": target, "error": f"timed out after {timeout:g}s"}
    except ConnectionRefusedError as exc:
        return {
            "target": target,
            "error": f"connection refused; start the Blender MCP add-on bridge on this port ({exc})",
        }
    except (OSError, OverflowError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"target": target, "error": str(exc)}


def read_code(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    if args.code is not None:
        code = args.code
    elif args.file is not None:
        try:
            code = args.file.read_text(encoding="utf-8")
        except OSError as exc:
            parser.error(f"cannot read {args.file}: {exc}")
    elif not sys.stdin.isatty():
        code = sys.stdin.read()
    else:
        parser.error("provide --code, --file, or pipe Python code on stdin")
    if not code.strip():
        parser.error("Python code is empty")
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute the same Python snippet in one or more running Blender instances "
            "through the Blender MCP add-on's local TCP bridge."
        ),
        epilog=(
            "This executes arbitrary Python inside each target Blender. Keep the add-on "
            "listener on loopback or another trusted network."
        ),
    )
    parser.add_argument("--host", default="localhost", help="host used by every port (default: localhost)")
    parser.add_argument(
        "--port",
        dest="ports",
        type=parse_port,
        action="append",
        required=True,
        help="Blender add-on listener port; repeat to target multiple instances concurrently",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--code", help="Python snippet to execute")
    source.add_argument("--file", type=Path, help="UTF-8 Python file to execute")
    parser.add_argument(
        "--timeout",
        type=parse_timeout,
        default=300.0,
        help="socket inactivity timeout in seconds (default: 300)",
    )
    args = parser.parse_args(argv)
    if len(set(args.ports)) != len(args.ports):
        parser.error("each --port must be unique; a port identifies one Blender instance")

    code = read_code(args, parser)
    try:
        request = make_request(code)
    except ValueError as exc:
        parser.error(str(exc))

    worker_count = min(len(args.ports), MAX_PARALLEL_TARGETS)
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = [pool.submit(execute_at, args.host, port, request, args.timeout) for port in args.ports]
        targets = [future.result() for future in futures]

    print(json.dumps({"targets": targets}, indent=2, ensure_ascii=False))
    return 0 if all(
        "response" in target and target["response"].get("status") == "ok"
        for target in targets
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
