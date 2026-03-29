# models.py
from __future__ import annotations
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field
from openenv.core.env_server import Action, Observation, State


# ──────────────────────────────────────────────
# SUB-MODEL: Task (plain BaseModel, NOT Observation)
# ──────────────────────────────────────────────

class TaskObservation(BaseModel):
    """Snapshot of one task as seen by the agent (may include noise)."""
    task_id: int
    title: str
    description: str
    status: Literal["not_started", "in_progress", "completed", "blocked"]
    progress: float                    # 0.0–1.0, possibly noisy
    planned_start_day: int
    planned_end_day: int
    priority: Literal["low", "medium", "high", "critical"]
    is_critical_path: bool
    dependencies: List[int]            # task_ids that must complete first
    blocked: bool
    required_workers: int
    assigned_workers: int
    required_materials: Dict[str, float]   # {"cement": 5.0}
    days_behind_schedule: int          # 0 if on time or not started


# ──────────────────────────────────────────────
# MAIN OBSERVATION
# ──────────────────────────────────────────────

class ConstructionObservation(Observation):
    """What the agent sees each step. Fields may be noisy."""
    # Inherited from Observation: done: bool, reward: Optional[float]
    day: int
    max_days: int
    tasks: List[TaskObservation]

    workers_available: int
    total_workers: int
    overtime_fatigue_level: float          # 0.0 (fresh) → 1.0 (burned out)

    materials_available: Dict[str, float]
    pending_orders: List[Dict]             # [{"type": "cement", "qty": 100, "arrives_day": 8}]

    weather: Literal["clear", "rain", "storm"]
    active_issues: List[str]               # ["worker_absent:3", "cement_delay"]

    budget_total: float
    budget_used: float                     # 0.0–1.0 ratio

    chat_messages: List[str]               # contextual PM advisor messages
    difficulty: Literal["easy", "medium", "hard"]
    reward_components: Optional[Dict[str, float]] = None


# ──────────────────────────────────────────────
# ACTION
# ──────────────────────────────────────────────

class ConstructionAction(Action):
    """One decision the agent makes per step (one day)."""
    action_type: Literal[
        "allocate_workers",      # assign N workers to a task
        "order_material",        # place a supply order
        "approve_overtime",      # extend working hours for a task
        "reschedule_task",       # move a task's planned start day
        "do_nothing",            # skip action (always valid)
        "request_pm_guidance",   # ask the senior PM for advice (costs 1 step of delay)
    ]
    task_id: Optional[int] = None
    worker_count: Optional[int] = None
    new_start_day: Optional[int] = None
    material_type: Optional[str] = None
    quantity: Optional[float] = None
    overtime_hours: Optional[int] = None
    message: Optional[str] = None


# ──────────────────────────────────────────────
# STATE (Hidden ground truth — server only)
# ──────────────────────────────────────────────

class MaterialOrder(BaseModel):
    material_type: str
    quantity: float
    arrival_day: int
    cost: float


class ConstructionState(State):
    """Ground truth state. Never sent to agent directly."""
    # Inherited from State: episode_id: Optional[str], step_count: int

    current_day: int = 1
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    max_days: int = 60

    # Ground truth progress (agent sees noisy version)
    true_task_progress: Dict[int, float] = Field(default_factory=dict)

    # Worker state
    worker_efficiency: float = 1.0        # 0.6 (tired) to 1.3 (motivated)
    overtime_fatigue: float = 0.0         # accumulates with overtime

    # Material pipeline
    pending_orders: List[MaterialOrder] = Field(default_factory=list)

    # Hidden upcoming events (agent doesn't see these)
    upcoming_disruptions: List[Dict] = Field(default_factory=list)

    # Equipment state
    equipment_health: Dict[str, float] = Field(default_factory=lambda: {"crane": 1.0, "excavator": 1.0})

    # Budget
    total_budget: float = 500_000.0
    total_cost: float = 0.0

    # Delay tracking
    total_delay_days: int = 0

    # Weather for this step (set once per step, used everywhere)
    current_weather: Literal["clear", "rain", "storm"] = "clear"
    # Active issues reported this step (exposed for observability)
    active_issues: List[str] = Field(default_factory=list)