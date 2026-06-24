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
        """Restore browser state from a previously saved file."""
        return self._run([self.binary, "--state", path, "--json"])

    # ── Snapshot ─────────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Get the current page's accessibility-tree snapshot.

        Returns the parsed JSON envelope::

            {
                "success": true,
                "data": {
                    "snapshot": "...",
                    "refs": {"e1": {"role": "...", "name": "..."}, ...}
                }
            }
        """
        cmd = [self.binary, "snapshot"] + self.snapshot_flags
        return self._run(cmd)

    def get_snapshot_text(self) -> str:
        """Return the compact snapshot text (the part fed to the LLM)."""
        result = self.snapshot()
        if result.get("success") and "data" in result:
            return result["data"].get("snapshot", "")
        return ""

    def get_refs(self) -> dict[str, dict[str, str]]:
        """Return the interactive element refs from the latest snapshot."""
        result = self.snapshot()
        if result.get("success") and "data" in result:
            return result["data"].get("refs", {})
        return {}

    # ── Actions ──────────────────────────────────────────────────────────

    def click(self, ref: str) -> dict[str, Any]:
        """Click an element by its @eN ref."""
        return self._run([self.binary, "click", ref, "--json"])

    def fill(self, ref: str, value: str) -> dict[str, Any]:
        """Fill a text field by its @eN ref."""
        return self._run([self.binary, "fill", ref, value, "--json"])

    def select(self, ref: str, value: str) -> dict[str, Any]:
        """Select a dropdown option by its @eN ref."""
        return self._run([self.binary, "select", ref, value, "--json"])

    def check(self, ref: str) -> dict[str, Any]:
        """Check a checkbox by its @eN ref."""
        return self._run([self.binary, "check", ref, "--json"])

    def type_text(self, ref: str, text: str) -> dict[str, Any]:
        """Type text into a field (keystroke-by-keystroke)."""
        return self._run([self.binary, "type", ref, text, "--json"])

    def press(self, key: str) -> dict[str, Any]:
        """Press a keyboard key (Enter, Tab, Escape, etc.)."""
        return self._run([self.binary, "press", key, "--json"])

    def scroll(self, direction: str = "down", amount: int = 3) -> dict[str, Any]:
        """Scroll the page."""
        return self._run([self.binary, "scroll", direction, str(amount), "--json"])

    # ── Navigation ───────────────────────────────────────────────────────

    def goto(self, url: str) -> dict[str, Any]:
        """Navigate to a URL."""
        return self._run([self.binary, "goto", url, "--json"])

    def back(self) -> dict[str, Any]:
        """Go back in browser history."""
        return self._run([self.binary, "back", "--json"])

    def wait(self, strategy: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Wait for page to settle."""
        strategy = strategy or self.default_wait
        cmd = [self.binary, "wait"]
        
        if strategy in ("networkidle", "load", "domcontentloaded"):
            cmd.extend(["--load", strategy])
        elif strategy.isdigit():
            cmd.append(strategy)
        else:
            import shlex
            cmd.extend(shlex.split(strategy))

        if "timeout" in kwargs:
            cmd += ["--timeout", str(kwargs["timeout"])]
        cmd.append("--json")
        return self._run(cmd)

    # ── Page info ────────────────────────────────────────────────────────

    def get_url(self) -> str:
        """Get the current page URL."""
        result = self._run([self.binary, "get", "url", "--json"])
        if result.get("success") and "data" in result:
            return result["data"].get("url", "")
        return ""

