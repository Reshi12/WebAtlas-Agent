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


