# server/modules/task_module.py
"""
Task Module — Core progress simulation for each construction task.

Key fixes vs original:
  - Crowding-aware worker scaling (n^0.85 / linear cap model)
  - Weather modifier is task-type-aware (indoor tasks immune)
  - Equipment health actually applied to progress
  - Material consumption separated cleanly from blocking check
  - Cement quality degradation applied
"""
from __future__ import annotations
from typing import Dict, List, Optional


# Tasks that are affected by outdoor weather
OUTDOOR_TASKS = {
    "Site Preparation",
    "Foundation",
    "Excavation",
    "Walls",
    "Roof",
    "Plastering",
    "Landscaping",
    "Structural Framing",
    "HVAC Installation",
    "Elevator Installation",
}

# Concrete tasks: cannot pour in rain at all
CONCRETE_TASKS = {
    "Foundation",
    "Structural Framing",
    "Walls",
}

# Tasks that depend on specific equipment
EQUIPMENT_DEPENDENT_TASKS: Dict[str, str] = {
    "Site Preparation": "excavator",
    "Foundation": "excavator",
    "Excavation": "excavator",
    "Structural Framing": "crane",
    "Walls": "crane",
    "Roof": "crane",
    "Elevator Installation": "crane",
}

# Crowding penalty parameter
LAMBDA_CROWD = 0.10


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
        required_materials: Dict[str, float],
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

    # ── Helpers ──────────────────────────────────────────

    def is_unblocked(self, all_tasks: Dict[int, "Task"]) -> bool:
        return all(all_tasks[d].true_progress >= 1.0 for d in self.dependencies)

    def days_behind(self, current_day: int) -> int:
        if self.true_progress >= 1.0:
            return 0
        if current_day > self.planned_end:
            return current_day - self.planned_end
        return 0

    # ── Weather modifier (task-type-aware) ───────────────

    def _effective_weather_modifier(
        self, weather_modifier: float, weather: str
    ) -> float:
        """
        Concrete pours stop completely in rain/storm.
        Outdoor tasks use the weather modifier.
        Indoor tasks are completely immune.
        """
        if self.title in CONCRETE_TASKS and weather in ("rain", "storm"):
            return 0.0
        if self.title not in OUTDOOR_TASKS:
            return 1.0  # indoor — immune
        return weather_modifier

    # ── Worker efficiency (crowding-aware) ────────────────

    def _effective_workers(self, assigned: int) -> float:
        """
        Crowding penalty: workers beyond optimal reduce productivity.
        effective = min(n, n_opt) + above_opt * max(0.4, 1 - λ * above_opt)
        """
        n_opt = max(1, self.required_workers)
        above_opt = max(0, assigned - n_opt)
        crowd_factor = max(0.4, 1.0 - LAMBDA_CROWD * above_opt)
        return min(assigned, n_opt) + above_opt * crowd_factor

    # ── Material check ────────────────────────────────────

    def _check_materials(
        self,
        materials_available: Dict[str, float],
        pending_orders: List,
        current_day: int,
        horizon: int,
    ):
        """
        Returns (fully_available, arriving_soon_list, blocking_list).
        Separates "arriving soon" (prep work OK) from "truly blocked".
        """
        blocking: List[str] = []
        arriving: List[str] = []
        for mat, rate in self.required_materials.items():
            need = rate * 0.1
            if materials_available.get(mat, 0.0) >= need:
                continue
            upcoming = [
                o for o in pending_orders
                if (o.get("material_type") if isinstance(o, dict) else o.material_type) == mat
                and (int(o.get("arrival_day", 9999)) if isinstance(o, dict)
                     else o.arrival_day) <= current_day + horizon
            ]
            if upcoming:
                arriving.append(mat)
            else:
                blocking.append(mat)

        fully_ok = len(blocking) == 0 and len(arriving) == 0
        return fully_ok, arriving, blocking

    def _consume_materials(
        self,
        materials_available: Dict[str, float],
        actual_gain: float,
    ) -> None:
        for mat, rate in self.required_materials.items():
            consume = rate * (actual_gain / 0.1)
            materials_available[mat] = max(
                0.0, materials_available.get(mat, 0.0) - consume
            )

    # ── Main progress update ──────────────────────────────

    def update_progress(
        self,
        current_day: int,
        all_tasks: Dict[int, "Task"],
        weather_modifier: float,
        weather: str,
        efficiency: float,
        materials_available: Dict[str, float],
        pending_orders: List,
        equipment_health: Optional[Dict[str, float]] = None,
        cement_quality: float = 1.0,
        prep_horizon_days: int = 5,
        prep_progress_cap: float = 0.10,
    ) -> float:
        """Returns progress gained this step. Also consumes materials."""

        # 1. Dependency check
        if not self.is_unblocked(all_tasks):
            self.blocked = True
            self.status = "blocked"
            return 0.0
        self.blocked = False

        # 2. Not scheduled yet
        if current_day < self.planned_start:
            self.status = "not_started"
            return 0.0

        # 3. No workers
        if self.assigned_workers == 0:
            if self.true_progress > 0:
                self.status = "in_progress"
            return 0.0

        # 4. Material check
        fully_ok, arriving, blocking = self._check_materials(
            materials_available, pending_orders, current_day, prep_horizon_days
        )
        if blocking:
            self.blocked = True
            self.status = "blocked"
            return 0.0

        # 5. Compute gain
        eff_workers = self._effective_workers(self.assigned_workers)
        base_gain = 0.02 * eff_workers

        eff_weather = self._effective_weather_modifier(weather_modifier, weather)

        # Equipment health modifier
        equip_modifier = 1.0
        if equipment_health:
            equip_key = EQUIPMENT_DEPENDENT_TASKS.get(self.title)
            if equip_key:
                equip_modifier = max(0.4, equipment_health.get(equip_key, 1.0))

        # Cement quality only relevant for cement-using tasks
        cement_factor = 1.0
        if "cement" in self.required_materials:
            cement_factor = max(0.0, min(1.0, cement_quality))

        gain = base_gain * efficiency * eff_weather * equip_modifier * cement_factor
        gain = max(0.0, gain)

        # 6. Apply progress
        old_progress = self.true_progress
        if arriving and not fully_ok:
            # Prep work — capped
            self.true_progress = min(
                min(1.0, prep_progress_cap), self.true_progress + gain
            )
        else:
            self.true_progress = min(1.0, self.true_progress + gain)

        actual_gain = self.true_progress - old_progress

        if actual_gain > 0:
            self.worker_hours_logged += self.assigned_workers * 8.0

        # 7. Consume materials (only when fully available)
        if actual_gain > 0 and fully_ok:
            self._consume_materials(materials_available, actual_gain)

        # 8. Update status
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

    def load(self, task_list: List[Task]) -> None:
        self.tasks = {t.task_id: t for t in task_list}

    def free_all_workers(self) -> None:
        for t in self.tasks.values():
            t.assigned_workers = 0

    def assign_workers(
        self, task_id: int, count: int, workers_available: int
    ) -> int:
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
        pending_orders: List,
        equipment_health: Optional[Dict[str, float]] = None,
        cement_quality: float = 1.0,
    ) -> float:
        total_gain = 0.0
        for task in self.tasks.values():
            gain = task.update_progress(
                current_day=current_day,
                all_tasks=self.tasks,
                weather_modifier=weather_modifier,
                weather=weather,
                efficiency=efficiency,
                materials_available=materials_available,
                pending_orders=pending_orders,
                equipment_health=equipment_health,
                cement_quality=cement_quality,
            )
            total_gain += gain
        return total_gain

    def total_delay_days(self, current_day: int) -> int:
        return sum(t.days_behind(current_day) for t in self.tasks.values())

    def all_complete(self) -> bool:
        return all(t.true_progress >= 1.0 for t in self.tasks.values())

    def get_critical_tasks_on_time(self, current_day: int):
        critical = [t for t in self.tasks.values() if t.is_critical_path]
        on_time = [t for t in critical if t.days_behind(current_day) == 0]
        return len(on_time), len(critical)
