"""CLI entrypoint for the autonomous browser agent.

Usage::

    python main.py "Compare iPhone 15 prices on Amazon, Flipkart, Croma; add cheapest to cart"
    python main.py --dry-run "Book a table at Bombay Canteen for 2 on Saturday"
    python main.py --resume task_20260623_2
    python main.py --list-tasks

Features:
  - Rich live-updating console with step trace and token counter
  - Backend-tagged output ([agent_browser] / [webwright])
  - Interrupt/resume via CLI prompts
  - Dry-run mode for plan-only execution
  - Task resume from saved state
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ── Bootstrap ────────────────────────────────────────────────────────────────

# Force UTF-8 on Windows so Rich can render emoji/Unicode correctly
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass  # Fallback: some CI environments don't support reconfigure

load_dotenv()

console = Console(force_terminal=True)


def setup_logging(verbose: bool = False) -> None:
