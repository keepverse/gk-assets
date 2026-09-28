"""Blender-side bootstrap used by blender_mcp_launch.py.

This script runs inside the newly launched Blender process. It starts the
installed Blender MCP add-on's existing TCP server on a process-specific port
without changing or saving the user's shared add-on preferences.
"""

from __future__ import annotations

import addon_utils
import importlib
import os
from pathlib import Path
import traceback

import bpy


def _log_error(message: str) -> None:
    print(f"GK_ASSETS_MCP_ERROR {message}", flush=True)


def _addon_candidates() -> dict[str, object]:
    """Find the MCP add-on whether Blender exposes it as legacy or extension API."""
    candidates = {
        module.__name__: module
        for module in addon_utils.modules(refresh=True)
        if hasattr(getattr(module, "mcp_to_blender_server", None), "start")
    }

    # Blender 4.2+ extensions are imported as bl_ext.<repository>.<extension>;
    # addon_utils.modules() does not reliably enumerate these in Blender 5.1.
    repositories = getattr(getattr(bpy.context.preferences, "extensions", None), "repos", ())
    for repository in repositories:
        repository_name = getattr(repository, "module", "")
        repository_path = getattr(repository, "directory", "")
        if not repository_name or not repository_path:
            continue
        if not (Path(repository_path) / "mcp" / "__init__.py").is_file():
            continue
        module_name = f"bl_ext.{repository_name}.mcp"
        module = importlib.import_module(module_name)
        if hasattr(getattr(module, "mcp_to_blender_server", None), "start"):
            candidates[module.__name__] = module
    return candidates


def _bootstrap() -> None:
    try:
        port = int(os.environ["GK_ASSETS_MCP_PORT"])
        host = os.environ.get("GK_ASSETS_MCP_HOST", "127.0.0.1")
        cancel_file = os.environ.get("GK_ASSETS_MCP_CANCEL_FILE", "")
        candidates = _addon_candidates()
        if len(candidates) != 1:
            names = ", ".join(candidates) or "none"
            raise RuntimeError(f"expected one installed Blender MCP add-on, found: {names}")

        module = next(iter(candidates.values()))
        addon_utils.enable(module.__name__, default_set=False, persistent=True)
        server = module.mcp_to_blender_server
        interactive = importlib.import_module(module.__name__ + ".execute_interactive")
    except Exception as exc:  # Keep Blender open so the user can inspect the startup log.
        traceback.print_exc()
        _log_error(f"could not load Blender MCP add-on: {exc}")
        return

    attempts = 0

    def start_bridge() -> float | None:
        nonlocal attempts
        if cancel_file and os.path.exists(cancel_file):
            print("GK_ASSETS_MCP_CANCELLED startup timed out in launcher", flush=True)
            return None

        try:
            # An enabled add-on may have auto-started on its shared default
            # port before this bootstrap ran. Replace that listener in this
            # process only; no preference is written back to disk.
            if server.is_running():
                server.stop()
            server.start(host, port)
        except OSError as exc:
            # The launcher briefly reserves this port while creating Blender,
            # and another process can also race for it. Retry before failing.
            attempts += 1
            if attempts < 120:
                return 0.25
            traceback.print_exc()
            _log_error(f"could not start bridge on {host}:{port}: {exc}")
            return None
        except Exception as exc:
            traceback.print_exc()
            _log_error(f"could not start bridge on {host}:{port}: {exc}")
            return None

        try:
            if not bpy.app.timers.is_registered(interactive.run):
                bpy.app.timers.register(
                    interactive.run,
                    first_interval=server.TIMER_INTERVAL_ACTIVE,
                    persistent=True,
                )
        except Exception as exc:
            server.stop()
            traceback.print_exc()
            _log_error(f"could not register Blender's bridge timer: {exc}")
            return None

        print(f"GK_ASSETS_MCP_READY {host} {port} {os.getpid()}", flush=True)
        return None

    try:
        bpy.app.timers.register(start_bridge, first_interval=0.25)
    except Exception as exc:
        traceback.print_exc()
        _log_error(f"could not schedule bridge startup: {exc}")


_bootstrap()
