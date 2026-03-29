from __future__ import annotations

from typing import Any, Optional

from models import ConstructionAction

from policies.issue_handling import handle_blocked_tasks, handle_material_issue, maybe_ask_pm
from policies.resource_allocation import allocate_all_workers


CURRENT_TASK_ID: Optional[int] = None


def reset_policy_state() -> None:
    global CURRENT_TASK_ID
    CURRENT_TASK_ID = None


def _priority_weight(priority: str) -> int:
    if priority == "critical":
        return 130
    if priority == "high":
        return 85
    if priority == "medium":
        return 40
    return 10


def _tasks_by_id(obs: Any) -> dict[int, Any]:
    return {t.task_id: t for t in obs.tasks}


def _pending_quantity(obs: Any, material: str, horizon_days: int = 4) -> float:
    total = 0.0
    current_day = int(getattr(obs, "day", 0))
    for order in (obs.pending_orders or []):
        if isinstance(order, dict):
            mat = order.get("material_type")
            qty = float(order.get("quantity", 0.0) or 0.0)
            arrival = int(order.get("arrival_day", current_day + 999))
            if mat == material and arrival <= current_day + horizon_days:
                total += qty
    return total


def _deps_complete(task: Any, tasks: dict[int, Any]) -> bool:
    return all((tasks.get(dep_id) is not None and tasks[dep_id].progress >= 1.0) for dep_id in task.dependencies)


def _has_materials(task: Any, obs: Any) -> bool:
    for mat, amount_per_10pct in (task.required_materials or {}).items():
        needed_now = amount_per_10pct * 0.1
        have = float((obs.materials_available or {}).get(mat, 0.0))
        if have < needed_now:
            return False
    return True


def _ready_tasks(obs: Any) -> list[Any]:
    tasks = _tasks_by_id(obs)
    ready = []
    for t in obs.tasks:
        if t.progress >= 1.0:
            continue
        if obs.day < t.planned_start_day:
            continue
        if not _deps_complete(t, tasks):
            continue
        if not _has_materials(t, obs):
            continue
        ready.append(t)
    return ready


def _ready_critical_tasks(obs: Any) -> list[Any]:
    return [t for t in _ready_tasks(obs) if t.is_critical_path]


def _reverse_dependency_count(task: Any, obs: Any) -> int:
    count = 0
    for other in obs.tasks:
        if task.task_id in other.dependencies and other.progress < 1.0:
            count += 1
    return count


def _unlock_potential(task: Any, obs: Any) -> float:
    # Reward tasks that unlock many downstream tasks, especially critical ones.
    downstream = _reverse_dependency_count(task, obs)
    critical_downstream = 0
    for other in obs.tasks:
        if task.task_id in other.dependencies and other.progress < 1.0 and other.is_critical_path:
            critical_downstream += 1
    return downstream * 25.0 + critical_downstream * 40.0


def _score_task(task: Any, obs: Any) -> float:
    score = 0.0
    late_stage = obs.day >= int(obs.max_days * 0.75)

    score += _priority_weight(task.priority)
    score += max(0, task.days_behind_schedule) * 60
    score += 35.0 if task.is_critical_path else 0.0
    score += _unlock_potential(task, obs)
    score += task.progress * 35.0

    # Late-stage sprint: strongly bias finishing already-progressed tasks.
    if late_stage:
        score += task.progress * 80.0
        if task.progress > 0.5:
            score += 70.0

    if task.progress > 0.7:
        score += 110.0
    return score


def _select_task(obs: Any) -> Optional[Any]:
    global CURRENT_TASK_ID

    critical_sprint = obs.day >= (obs.max_days - 20)
    ready = _ready_critical_tasks(obs) if critical_sprint else _ready_tasks(obs)
    if critical_sprint and not ready:
        ready = _ready_tasks(obs)
    if not ready:
        return None

    if CURRENT_TASK_ID is not None:
        for t in ready:
            if t.task_id == CURRENT_TASK_ID:
                return t

    return max(ready, key=lambda t: _score_task(t, obs))


def _prefetch_successor_materials(obs: Any) -> Optional[ConstructionAction]:
    tasks = _tasks_by_id(obs)
    shortages: dict[str, float] = {}

    # Prefetch for tasks that are near-unlock: exactly one dependency not complete.
    for t in obs.tasks:
        if t.progress >= 1.0:
            continue
        if obs.day >= t.planned_end_day:
            continue

        unmet = []
        for dep_id in t.dependencies:
            dep = tasks.get(dep_id)
            if dep is None or dep.progress < 1.0:
                unmet.append(dep)

        # Near-unlock if all deps complete, or only one dep remains and it's almost done.
        near_unlock = False
        if len(unmet) == 0:
            near_unlock = True
        elif len(unmet) == 1 and unmet[0] is not None and unmet[0].progress >= 0.8:
            near_unlock = True

        if not near_unlock:
            continue

        for mat, amount_per_10pct in (t.required_materials or {}).items():
            need = amount_per_10pct * 0.2
            have = float((obs.materials_available or {}).get(mat, 0.0)) + _pending_quantity(obs, mat, horizon_days=5)
            if have < need:
                shortages[mat] = shortages.get(mat, 0.0) + (need - have)

    if shortages:
        material = max(shortages.items(), key=lambda kv: kv[1])[0]
        deficit = shortages[material]
        quantity = min(300, max(60, int(deficit * 100)))
        return ConstructionAction(
            action_type="order_material",
            material_type=material,
            quantity=quantity,
        )

    return None


def _emergency_material_topup(obs: Any) -> Optional[ConstructionAction]:
    tasks = _tasks_by_id(obs)
    shortages: dict[str, float] = {}

    # If no ready tasks exist, blocked dependency-ready tasks likely need materials.
    for t in obs.tasks:
        if t.progress >= 1.0:
            continue
        if _has_materials(t, obs):
            continue
        if not _deps_complete(t, tasks):
            continue
        for mat, amount_per_10pct in (t.required_materials or {}).items():
            have = float((obs.materials_available or {}).get(mat, 0.0))
            need = amount_per_10pct * 0.1
            if have < need:
                shortages[mat] = shortages.get(mat, 0.0) + (need - have)

    if shortages:
        material = max(shortages.items(), key=lambda kv: kv[1])[0]
        return ConstructionAction(
            action_type="order_material",
            material_type=material,
            quantity=120,
        )

    return None


def smart_policy(obs: Any) -> ConstructionAction:
    global CURRENT_TASK_ID

    # 1) Execute feasible work first.
    task = _select_task(obs)
    if task is not None:
        CURRENT_TASK_ID = task.task_id
        # Always approve overtime if critical or behind schedule and not too fatigued
        if (task.is_critical_path or task.days_behind_schedule > 0) and obs.overtime_fatigue_level < 0.5:
            overtime_action = ConstructionAction(
                action_type="approve_overtime",
                task_id=task.task_id,
                overtime_hours=2,
            )
            return overtime_action
        
        return ConstructionAction(
            action_type="allocate_workers",
            task_id=task.task_id,
            worker_count=obs.workers_available,
        )

    # 2) If stalled, resolve supply constraints.
    # prefetch_action = _prefetch_successor_materials(obs)
    # if prefetch_action is not None:
    #     return prefetch_action

    # 3) If stalled, resolve immediate supply constraints.
    material_action = handle_material_issue(obs)
    if material_action is not None:
        return material_action

    # 4) Pull forward dependency-ready future tasks.
    reschedule_action = handle_blocked_tasks(obs)
    if reschedule_action is not None:
        return reschedule_action

    # 5) Emergency top-up to avoid idle deadlocks when nothing is executable.
    emergency_material = _emergency_material_topup(obs)
    if emergency_material is not None:
        return emergency_material

    # 6) Escalate only when genuinely constrained.
    pm_action = maybe_ask_pm(obs)
    if pm_action is not None:
        return pm_action

    return ConstructionAction(action_type="do_nothing")
