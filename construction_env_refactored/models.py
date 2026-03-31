# models.py
"""
Construction RL Environment — Data Models
Fully typed Pydantic models for Action, Observation, and State.
"""
from __future__ import annotations
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field
from openenv.core.env_server import Action, Observation, State


# ──────────────────────────────────────────────
# SUB-MODELS
# ──────────────────────────────────────────────

class TaskObservation(BaseModel):
    """Snapshot of one task as seen by the agent (may include Gaussian noise on progress)."""
    task_id: int
    title: str
    description: str
    status: Literal["not_started", "in_progress", "completed", "blocked"]
    progress: float                        # 0.0–1.0, possibly noisy
    planned_start_day: int
    planned_end_day: int
    priority: Literal["low", "medium", "high", "critical"]
    is_critical_path: bool
    dependencies: List[int]               # task_ids that must complete first
    blocked: bool
    required_workers: int
    assigned_workers: int
    required_materials: Dict[str, float]  # {"cement": 5.0} = units per 10% progress
    days_behind_schedule: int
    estimated_completion_day: Optional[int] = None
    worker_hours_logged: float = 0.0
    rework_count: int = 0


# ──────────────────────────────────────────────
# MAIN OBSERVATION
# ──────────────────────────────────────────────

class ConstructionObservation(Observation):
    """
    What the agent sees each step. Fields may be noisy.
    Inherited from Observation: done: bool, reward: Optional[float]
    """
    day: int
    max_days: int
    tasks: List[TaskObservation]

    workers_available: int
    total_workers: int
    overtime_fatigue_level: float          # 0.0 (fresh) → 1.0 (burned out)

    materials_available: Dict[str, float]
    pending_orders: List[Dict]             # serialised MaterialOrder list

    weather: Literal["clear", "rain", "storm"]
    active_issues: List[str]               # ["worker_absent:3", "equipment_degraded:crane"]

    budget_total: float
    budget_used: float                     # ratio 0.0–1.0+ (can exceed 1 on overrun)

    chat_messages: List[str]
    difficulty: Literal["easy", "medium", "hard"]

    # Convenience aggregates
    reward_components: Optional[Dict[str, float]] = None
    equipment_health: Dict[str, float] = Field(default_factory=dict)
    critical_path_tasks: List[int] = Field(default_factory=list)
    days_remaining: int = 0
    overall_progress: float = 0.0
    idle_workers_ratio: float = 0.0
    overtime_hours: float = 0.0
    material_waste: float = 0.0
    delay_penalty: float = 0.0
    cement_quality: float = 1.0


# ──────────────────────────────────────────────
# ACTION
# ──────────────────────────────────────────────

class Allocation(BaseModel):
    task_id: int
    worker_count: int


class ActionStep(BaseModel):
    """One sub-action inside a multi_action envelope."""
    action_type: Literal[
        "allocate_workers",
        "allocate_workers_batch",
        "order_material",
        "approve_overtime",
        "reschedule_task",
        "do_nothing",
        "request_pm_guidance",
    ]
    task_id: Optional[int] = None
    worker_count: Optional[int] = None
    allocations: Optional[List[Allocation]] = None
    new_start_day: Optional[int] = None
    material_type: Optional[str] = None
    quantity: Optional[float] = None
    overtime_hours: Optional[int] = None
    message: Optional[str] = None


class ConstructionAction(Action):
    """One decision the agent makes per step (one day)."""
    action_type: Literal[
        "allocate_workers",
        "allocate_workers_batch",
        "order_material",
        "approve_overtime",
        "reschedule_task",
        "do_nothing",
        "request_pm_guidance",
        "multi_action",
    ]
    task_id: Optional[int] = None
    worker_count: Optional[int] = None
    allocations: Optional[List[Allocation]] = None
    new_start_day: Optional[int] = None
    material_type: Optional[str] = None
    quantity: Optional[float] = None
    overtime_hours: Optional[int] = None
    message: Optional[str] = None
    actions: Optional[List[ActionStep]] = None


# ──────────────────────────────────────────────
# MATERIAL ORDER
# ──────────────────────────────────────────────

class MaterialOrder(BaseModel):
    material_type: str
    quantity: float
    arrival_day: int
    cost: float


# ──────────────────────────────────────────────
# STATE (hidden ground truth — server only)
# ──────────────────────────────────────────────

class ConstructionState(State):
    """
    Ground truth state — never sent to agent directly.
    Inherited from State: episode_id: Optional[str], step_count: int
    """
    current_day: int = 1
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    max_days: int = 180

    true_task_progress: Dict[int, float] = Field(default_factory=dict)

    worker_efficiency: float = 1.0
    overtime_fatigue: float = 0.0

    pending_orders: List[MaterialOrder] = Field(default_factory=list)
    upcoming_disruptions: List[Dict] = Field(default_factory=list)

    equipment_health: Dict[str, float] = Field(
        default_factory=lambda: {"crane": 1.0, "excavator": 1.0}
    )

    total_budget: float = 500_000.0
    total_cost: float = 0.0

    total_delay_days: int = 0

    # KPI accumulators
    last_action_count: int = 0
    last_overtime_hours: float = 0.0
    last_material_waste: float = 0.0
    cumulative_overtime_hours: float = 0.0
    cumulative_idle_workers: int = 0
    cumulative_material_waste: float = 0.0
    cumulative_action_count: int = 0
    cumulative_multi_action_count: int = 0
    cumulative_bad_action_count: int = 0
    cumulative_zero_progress_days: int = 0

    current_weather: Literal["clear", "rain", "storm"] = "clear"
    active_issues: List[str] = Field(default_factory=list)
