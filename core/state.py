"""AgentState schema for the browser agent LangGraph state machine.

This is the single source of truth for all state carried through the graph.
Every node reads from and writes partial updates back to this state.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages


# ── Supporting types ─────────────────────────────────────────────────────────


class PlanStep(TypedDict):
    """A single step in the agent's execution plan."""

    step: str  # human-readable description of what to do
    backend: Literal["agent_browser", "webwright"]  # which backend executes this
    details: str  # additional context for the backend


class StepRecord(TypedDict, total=False):
    """Record of a single executed step, stored in step_history."""

    step: str
    backend: Literal["agent_browser", "webwright"]
    action: str  # the concrete action taken (e.g., "click @e12", "ran script")
    result: str  # what happened after the action
    success: bool
    attempt: int  # 1-indexed retry count
    tokens_used: int
    screenshot_path: str | None


class PageClassification(TypedDict, total=False):
    """Result of the safety gate's page analysis."""

    is_payment_page: bool
    is_login_page: bool
    has_personal_info_fields: bool
    agent_fillable_fields: list[str]
    human_required_fields: list[str]
    reason: str


# ── Main state schema ────────────────────────────────────────────────────────


class AgentState(TypedDict, total=False):
    """Full state carried through the LangGraph execution graph.

    Every field uses ``total=False`` so nodes can return partial updates
    containing only the keys they modify — LangGraph merges them.
    """

    # ── Task & plan ──────────────────────────────────────────────────────
    task: str  # original user instruction
    plan: list[PlanStep]  # planner output: ordered steps with backend tags
    current_step_index: int  # which step we're on (0-indexed)
    step_history: list[StepRecord]  # audit trail of every action taken

    # ── Page context ─────────────────────────────────────────────────────
    page_url: str
    page_domain: str
    page_snapshot: str  # compact a11y-tree ref dump from agent-browser
    page_classification: PageClassification | None

    # ── Execution control ────────────────────────────────────────────────
    status: Literal[
        "running",
        "awaiting_human",
        "awaiting_payment_resume",
        "failed",
        "done",
    ]
    interrupt_reason: str | None  # "personal_info" | "login" | "payment" | "ambiguous" | "destructive"
    interrupt_message: str | None
    retry_count: int
    max_retries: int
    used_strong_model_this_step: bool

    # ── Token tracking ───────────────────────────────────────────────────
    tokens_by_backend: dict[str, int]  # {"agent_browser": N, "webwright": M}

    # ── Persistence ──────────────────────────────────────────────────────
    task_id: str

    # ── Error state ──────────────────────────────────────────────────────
    last_action_screenshot: str | None
    error_message: str | None

    # ── Dry-run mode ─────────────────────────────────────────────────────
    dry_run: bool


def make_initial_state(task: str, task_id: str, *, max_retries: int = 2, dry_run: bool = False) -> AgentState:
    """Create a fresh AgentState with sane defaults for a new task."""
    return AgentState(
        task=task,
        plan=[],
        current_step_index=0,
        step_history=[],
        page_url="",
        page_domain="",
        page_snapshot="",
        page_classification=None,
        status="running",
        interrupt_reason=None,
        interrupt_message=None,
        retry_count=0,
        max_retries=max_retries,
        used_strong_model_this_step=False,
        tokens_by_backend={"agent_browser": 0, "webwright": 0},
        task_id=task_id,
        last_action_screenshot=None,
        error_message=None,
        dry_run=dry_run,
    )
