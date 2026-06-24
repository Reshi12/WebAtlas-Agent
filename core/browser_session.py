"""Thin wrapper around agent-browser's session management.

Uses agent-browser's native ``--session-name``, ``state save``, and
``--profile`` flags. No custom session JSON — agent-browser handles
cookie/session persistence itself.
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class BrowserSession:
    """Manages agent-browser sessions for login persistence and state reuse."""

    def __init__(self, config: dict[str, Any]):
        import shutil
        ab_cfg = config.get("agent_browser", {})
        raw_binary = ab_cfg.get("binary", "agent-browser")
        self.binary: str = shutil.which(raw_binary) or raw_binary
        self.default_wait: str = ab_cfg.get("default_wait", "networkidle")
        self.wait_timeout_ms: int = ab_cfg.get("wait_timeout_ms", 30000)
        self.snapshot_flags: list[str] = ab_cfg.get("snapshot_flags", ["-i", "--json"])
        self._current_session: str | None = None

    # ── Session lifecycle ────────────────────────────────────────────────

    def open(self, url: str, session_name: str | None = None) -> dict[str, Any]:
        """Open a URL in agent-browser, optionally reusing a named session.

        If ``session_name`` is provided, uses ``--session-name`` for cookie
        persistence (login reuse without credential auto-fill).
        """
        cmd = [self.binary]
        if session_name:
            cmd += ["--session-name", session_name]
            self._current_session = session_name
        cmd += ["open", url, "--json"]

        return self._run(cmd)

    def save_state(self, path: str) -> dict[str, Any]:
        """Save current browser state to a file for later resume."""
        return self._run([self.binary, "state", "save", path, "--json"])

    def load_state(self, path: str) -> dict[str, Any]:
