# server/modules/task_module.py
from __future__ import annotations
from typing import Dict, List, Optional
import random


OUTDOOR_TASKS = {
    "Site Preparation",
    "Foundation",
    "Excavation",
    "Walls",
    "Roof",
    "Plastering",
    "Landscaping",
}

CONCRETE_TASKS = {
    "Foundation",
    "Structural Framing",
    "Walls",
}

EQUIPMENT_DEPENDENT_TASKS = {
    "Site Preparation": "excavator",
    "Foundation": "excavator",
    "Structural Framing": "crane",
    "Walls": "crane",
    "Roof": "crane",
}


class Task:
    def __init__(
        self,
        task_id: int,
        title: str,
        description: str,
        planned_start: int,
        planned_end: int,
        dependencies: List[int],
        required_workers: int,
        required_materials: Dict[str, float],   # consumed per 10% of progress
        is_critical_path: bool,
        priority: str,
    ):
        self.task_id = task_id
        self.title = title
        self.description = description
        self.planned_start = planned_start
        self.planned_end = planned_end
        self.dependencies = dependencies
        self.required_workers = required_workers
        self.required_materials = required_materials
        self.is_critical_path = is_critical_path
        self.priority = priority

        # Runtime state
        self.true_progress: float = 0.0
        self.assigned_workers: int = 0
        self.blocked: bool = False
        self.status: str = "not_started"
        self.actual_start: Optional[int] = None
        self.actual_end: Optional[int] = None
        self.worker_hours_logged: float = 0.0
        self.rework_count: int = 0

    def is_unblocked(self, all_tasks: Dict[int, "Task"]) -> bool:
        return all(all_tasks[d].true_progress >= 1.0 for d in self.dependencies)

    def days_behind(self, current_day: int) -> int:
        if self.true_progress >= 1.0:
            return 0
        if current_day > self.planned_end:
            return current_day - self.planned_end
        return 0

    def update_progress(
        self,
        current_day: int,
        all_tasks: Dict[int, "Task"],
        weather_modifier: float,
        weather: str,
        efficiency: float,
        materials_available: Dict[str, float],
        pending_orders: List["MaterialOrder"],
        equipment_health: Optional[Dict[str, float]] = None,
        cement_quality: float = 1.0,
        prep_horizon_days: int = 5,
        prep_progress_cap: float = 0.1,
    ) -> float:
        """Returns progress gained this step. Also consumes materials."""
        # Dependency check
        if not self.is_unblocked(all_tasks):
            self.blocked = True
            self.status = "blocked"
            return 0.0

        self.blocked = False

        # Not started yet
        if current_day < self.planned_start:
            self.status = "not_started"
            return 0.0

        # No workers assigned
        if self.assigned_workers == 0:
            if self.true_progress > 0:
                self.status = "in_progress"
            return 0.0

        # Check materials available or arriving soon (prep work allowed).
        blocking_missing: List[str] = []
        arriving_missing: List[str] = []
        for mat, amount_per_10pct in self.required_materials.items():
            if materials_available.get(mat, 0) >= amount_per_10pct * 0.1:
                continue
            arrivals = [
                o.arrival_day
                for o in pending_orders
                if o.material_type == mat
            ]
            if arrivals and min(arrivals) <= current_day + prep_horizon_days:
                arriving_missing.append(mat)
            else:
                blocking_missing.append(mat)

        if blocking_missing:
            self.blocked = True
            self.status = "blocked"
            return 0.0

        # Compute progress gain
        n_opt = max(1, self.required_workers)
        above_opt = max(0, self.assigned_workers - n_opt)
        crowd_factor = max(0.4, 1.0 - (0.10 * above_opt))
        effective_workers = min(self.assigned_workers, n_opt) + (above_opt * crowd_factor)
        base_gain = 0.02 * effective_workers

        if self.title in CONCRETE_TASKS and weather in ("rain", "storm"):
            effective_weather = 0.0
        elif self.title not in OUTDOOR_TASKS:
            effective_weather = 1.0
        else:
            effective_weather = weather_modifier

        equip_modifier = 1.0
        if equipment_health:
            equip_key = EQUIPMENT_DEPENDENT_TASKS.get(self.title)
            if equip_key:
                equip_modifier = max(0.4, equipment_health.get(equip_key, 1.0))

        cement_factor = max(0.0, min(1.0, cement_quality))
        if "cement" not in self.required_materials:
            cement_factor = 1.0

        gain = base_gain * efficiency * effective_weather * equip_modifier * cement_factor
        gain = max(0.0, gain)

        old_progress = self.true_progress
        if arriving_missing:
            # Allow limited prep work before materials arrive.
            prep_limit = min(1.0, prep_progress_cap)
            self.true_progress = min(prep_limit, self.true_progress + gain)
        else:
            self.true_progress = min(1.0, self.true_progress + gain)
        actual_gain = self.true_progress - old_progress

        if actual_gain > 0:
            self.worker_hours_logged += self.assigned_workers * 8.0

        # Consume materials proportional to progress gain
        if actual_gain > 0 and not arriving_missing:
            for mat, amount_per_10pct in self.required_materials.items():
                consume = amount_per_10pct * (actual_gain / 0.1)
                materials_available[mat] = max(0.0, materials_available.get(mat, 0) - consume)

        # Update status
        if self.true_progress >= 1.0:
            self.status = "completed"
            self.actual_end = current_day
        else:
            if self.actual_start is None:
                self.actual_start = current_day
            self.status = "in_progress"

        return actual_gain


class TaskModule:
    def __init__(self):
        self.tasks: Dict[int, Task] = {}

    def load(self, task_list: List[Task]):
        self.tasks = {t.task_id: t for t in task_list}

    def free_all_workers(self):
        for t in self.tasks.values():
            t.assigned_workers = 0

    def assign_workers(self, task_id: int, count: int, workers_available: int) -> int:
        """Returns actual number assigned (capped by availability)."""
        task = self.tasks.get(task_id)
        if not task:
            return 0
        actual = min(count, workers_available)
        task.assigned_workers = actual
        return actual

    def update_all(
        self,
        current_day: int,
        weather_modifier: float,
        weather: str,
        efficiency: float,
        materials_available: Dict[str, float],
        pending_orders: List["MaterialOrder"],
        equipment_health: Optional[Dict[str, float]] = None,
        cement_quality: float = 1.0,
    ) -> float:
        total_gain = 0.0
        for task in self.tasks.values():
            gain = task.update_progress(
                current_day,
                self.tasks,
                weather_modifier,
                weather,
                efficiency,
                materials_available,
                pending_orders,
                equipment_health,
                cement_quality,
            )
            total_gain += gain
        return total_gain

    def total_delay_days(self, current_day: int) -> int:
        return sum(t.days_behind(current_day) for t in self.tasks.values())

    def all_complete(self) -> bool:
        return all(t.true_progress >= 1.0 for t in self.tasks.values())

    def get_critical_tasks_on_time(self, current_day: int) -> tuple:
        critical = [t for t in self.tasks.values() if t.is_critical_path]
        on_time = [t for t in critical if t.days_behind(current_day) == 0]
        return len(on_time), len(critical)