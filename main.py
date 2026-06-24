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
    """Configure logging with Rich handler."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )
    # Suppress noisy third-party loggers
    for name in ("httpx", "httpcore", "openai", "groq", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)


def load_config(path: str = "config.yaml") -> dict[str, Any]:
    """Load the YAML configuration file."""
    if not os.path.exists(path):
        console.print(f"[red]Config file not found: {path}[/red]")
        console.print("Copy config.yaml.example to config.yaml and configure it.")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Display helpers ──────────────────────────────────────────────────────────


def print_banner() -> None:
    """Print the startup banner."""
    banner = Text()
    banner.append("🤖 ", style="bold")
    banner.append("Autonomous Browser Agent", style="bold cyan")
    banner.append(" v1.0", style="dim")
    console.print(Panel(banner, border_style="cyan"))


def print_plan(plan: list[dict[str, Any]]) -> None:
    """Display the execution plan as a formatted table."""
    console.print("\n📋 [bold]Execution Plan[/bold]")
    table = Table(show_header=True, header_style="bold magenta", padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("Backend", style="cyan", width=16)
    table.add_column("Step", style="white")

    for i, step in enumerate(plan, 1):
        backend = step.get("backend", "?")
        icon = "🌐" if backend == "agent_browser" else "🔎"
        table.add_row(
            str(i),
            f"{icon} {backend}",
            step.get("step", ""),
        )
    console.print(table)
    console.print()


def print_step_start(idx: int, total: int, backend: str, step: str) -> None:
    """Print a step-start indicator."""
    icon = "🌐" if backend == "agent_browser" else "🔎"
    console.print(
        f"{icon} [bold][Step {idx + 1}/{total} · {backend}][/bold] {step}"
    )


def print_step_result(record: dict[str, Any]) -> None:
    """Print the result of a completed step."""
    success = record.get("success", False)
    if success:
        console.print(f"  ✅ {record.get('result', 'Done')[:200]}")
    else:
        console.print(f"  ❌ {record.get('result', 'Failed')[:200]}")


def print_interrupt(reason: str, message: str) -> None:
    """Display an interrupt message and prompt for input."""
    style = "red" if reason == "payment" else "yellow"
    console.print(Panel(message, title="Agent Paused", border_style=style))


def print_token_summary(tokens: dict[str, int], llm_tokens: dict[str, int]) -> None:
    """Print the final token usage summary."""
    console.print("\n📊 [bold]Token Usage[/bold]")
    table = Table(show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("Category", style="cyan")
    table.add_column("Tokens", style="green", justify="right")

    ab = tokens.get("agent_browser", 0)
    ww = tokens.get("webwright", 0)
    total = ab + ww

    table.add_row("agent-browser", f"{ab:,}")
    table.add_row("webwright", f"{ww:,}")
    table.add_row("LLM tokens", f"{llm_tokens.get('total', 0):,}")
    table.add_row("[bold]Total[/bold]", f"[bold]{total:,}[/bold]")

    console.print(table)


def print_task_list(tasks: list[dict[str, Any]]) -> None:
    """Display saved tasks for resume."""
    if not tasks:
        console.print("[dim]No saved tasks found.[/dim]")
        return
