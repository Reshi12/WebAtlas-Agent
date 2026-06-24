"""Save / load task state to disk for resume support.

Each task gets a JSON file under ``logs/<task_id>/state.json`` containing
the full AgentState. This allows resuming after a crash, manual payment,
or any human-interrupt handoff.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from core.state import AgentState

logger = logging.getLogger(__name__)

_LOG_DIR = "logs"


def _state_path(task_id: str) -> str:
    """Return the file path for a task's persisted state."""
    return os.path.join(_LOG_DIR, task_id, "state.json")


def _log_dir(task_id: str) -> str:
    """Return the log directory for a task."""
    return os.path.join(_LOG_DIR, task_id)


def save_state(state: AgentState) -> str:
    """Persist the current AgentState to disk.

    Returns the path of the saved file.
    """
    task_id = state.get("task_id", "unknown")
    path = _state_path(task_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Add metadata
    data: dict[str, Any] = dict(state)
    data["_saved_at"] = datetime.now(timezone.utc).isoformat()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

    logger.info("State saved to %s", path)
    return path


def load_state(task_id: str) -> AgentState | None:
    """Load a previously saved AgentState from disk.

    Returns None if no saved state exists for the given task_id.
    """
    path = _state_path(task_id)
    if not os.path.exists(path):
        logger.info("No saved state found for task %s", task_id)
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Strip metadata keys
    data.pop("_saved_at", None)
    logger.info("State loaded from %s", path)
    return data  # type: ignore[return-value]


def save_step_log(task_id: str, step_record: dict[str, Any]) -> None:
    """Append a step record to the task's step log (JSONL format)."""
    log_path = os.path.join(_log_dir(task_id), "steps.jsonl")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    record = {**step_record, "_timestamp": datetime.now(timezone.utc).isoformat()}
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def save_screenshot(task_id: str, filename: str, data: bytes) -> str:
    """Save a screenshot to the task's log directory.

    Returns the path of the saved screenshot.
    """
    dirpath = os.path.join(_log_dir(task_id), "screenshots")
    os.makedirs(dirpath, exist_ok=True)
    path = os.path.join(dirpath, filename)
    with open(path, "wb") as f:
        f.write(data)
    logger.debug("Screenshot saved: %s", path)
    return path


def list_saved_tasks() -> list[dict[str, Any]]:
