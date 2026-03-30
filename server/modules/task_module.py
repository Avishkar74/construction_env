# server/modules/task_module.py
from __future__ import annotations
from typing import Dict, List, Optional
import random


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
        efficiency: float,
        materials_available: Dict[str, float],
        pending_orders: List["MaterialOrder"],
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
        missing_now = []
        for mat, amount_per_10pct in self.required_materials.items():
            if materials_available.get(mat, 0) < amount_per_10pct * 0.1:
                missing_now.append(mat)

        if missing_now:
            arrivals = {o.material_type: o.arrival_day for o in pending_orders}
            for mat in list(missing_now):
                arrival_day = arrivals.get(mat)
                if arrival_day is not None and arrival_day <= current_day + prep_horizon_days:
                    missing_now.remove(mat)

        if missing_now:
            self.blocked = True
            self.status = "blocked"
            return 0.0

        # Compute progress gain
        # Base: 0.02 per worker per day, scaled by efficiency and weather
        base_gain = 0.02 * self.assigned_workers
        gain = base_gain * efficiency * weather_modifier
        gain = max(0.0, gain)

        old_progress = self.true_progress
        if missing_now:
            # Allow limited prep work before materials arrive.
            prep_limit = min(1.0, prep_progress_cap)
            self.true_progress = min(prep_limit, self.true_progress + gain)
        else:
            self.true_progress = min(1.0, self.true_progress + gain)
        actual_gain = self.true_progress - old_progress

        # Consume materials proportional to progress gain
        if actual_gain > 0 and not missing_now:
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
        efficiency: float,
        materials_available: Dict[str, float],
        pending_orders: List["MaterialOrder"],
    ) -> float:
        total_gain = 0.0
        for task in self.tasks.values():
            gain = task.update_progress(
                current_day,
                self.tasks,
                weather_modifier,
                efficiency,
                materials_available,
                pending_orders,
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