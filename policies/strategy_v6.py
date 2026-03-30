from __future__ import annotations

from typing import Any, Optional

from models import Allocation, ConstructionAction

CURRENT_TASK_ID: Optional[int] = None


def reset_policy_state() -> None:
    global CURRENT_TASK_ID
    CURRENT_TASK_ID = None


def _tasks_by_id(obs: Any) -> dict[int, Any]:
    return {t.task_id: t for t in obs.tasks}


def _deps_complete(task: Any, tasks: dict[int, Any]) -> bool:
    return all((tasks.get(dep_id) is not None and tasks[dep_id].progress >= 1.0) for dep_id in task.dependencies)


def _has_min_materials(task: Any, obs: Any) -> bool:
    for mat, amount_per_10pct in (task.required_materials or {}).items():
        if (obs.materials_available or {}).get(mat, 0.0) < amount_per_10pct * 0.1:
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
        if not _has_min_materials(t, obs):
            continue
        if t.blocked:
            continue
        ready.append(t)
    return ready


def _task_score(t: Any) -> float:
    score = 0.0
    if t.priority == "critical":
        score += 100.0
    elif t.priority == "high":
        score += 70.0
    elif t.priority == "medium":
        score += 40.0

    remaining = (1.0 - t.progress) * max(1, t.required_workers)
    score += remaining * 10.0
    score += max(0, t.days_behind_schedule) * 50.0
    if t.progress > 0.6:
        score += 80.0
    return score


def _compute_batch_allocations(obs: Any) -> list[Allocation]:
    workers = obs.workers_available
    tasks = _ready_tasks(obs)
    if not tasks or workers <= 0:
        return []

    tasks.sort(key=_task_score, reverse=True)
    allocations: list[Allocation] = []

    for idx, t in enumerate(tasks):
        if workers <= 0:
            break
        min_needed = max(1, t.required_workers)
        if workers < min_needed:
            continue

        assign = min(workers, min_needed)
        if idx == 0:
            assign = min(workers, max(min_needed, int(min_needed * 2)))
        elif idx == 1:
            assign = min(workers, max(min_needed, int(min_needed * 1.5)))

        if t.progress > 0.7:
            assign = workers

        allocations.append(Allocation(task_id=t.task_id, worker_count=assign))
        workers -= assign

    return allocations


def _get_pending_quantity(obs: Any, material: str) -> float:
    qty = 0.0
    for order in (obs.pending_orders or []):
        mat = order.get("material_type") if isinstance(order, dict) else order.material_type
        amount = float(order.get("quantity", 0.0) if isinstance(order, dict) else order.quantity)
        if mat == material:
            qty += amount
    return qty


def _handle_just_in_time_materials(obs: Any) -> Optional[ConstructionAction]:
    tasks = _tasks_by_id(obs)
    shortages: dict[str, float] = {}

    for task in obs.tasks:
        if task.progress >= 1.0:
            continue
        if obs.day < task.planned_start_day:
            continue
        if not _deps_complete(task, tasks):
            continue

        remaining_progress = 1.0 - task.progress
        for mat, amt_per_10pct in (task.required_materials or {}).items():
            needed_to_finish = amt_per_10pct * (remaining_progress * 10.0)
            have = (obs.materials_available or {}).get(mat, 0.0)
            pending = _get_pending_quantity(obs, mat)
            if have + pending < needed_to_finish:
                shortages[mat] = shortages.get(mat, 0.0) + (needed_to_finish - (have + pending))

    if shortages:
        material = max(shortages.items(), key=lambda kv: kv[1])[0]
        quantity = max(30.0, shortages[material] * 1.1)
        return ConstructionAction(
            action_type="order_material",
            material_type=material,
            quantity=quantity,
        )

    return None


def _prefetch_near_unlock_materials(obs: Any) -> Optional[ConstructionAction]:
    tasks = _tasks_by_id(obs)
    shortages: dict[str, float] = {}

    for t in obs.tasks:
        if t.progress >= 1.0:
            continue

        unmet = []
        for dep_id in t.dependencies:
            dep = tasks.get(dep_id)
            if dep is None or dep.progress < 1.0:
                unmet.append(dep)

        near_unlock = False
        if len(unmet) == 0:
            near_unlock = True
        elif len(unmet) == 1 and unmet[0] is not None and unmet[0].progress >= 0.8:
            near_unlock = True

        if not near_unlock:
            continue

        for mat, amount_per_10pct in (t.required_materials or {}).items():
            need = amount_per_10pct * 0.2
            have = float((obs.materials_available or {}).get(mat, 0.0)) + _get_pending_quantity(obs, mat)
            if have < need:
                shortages[mat] = shortages.get(mat, 0.0) + (need - have)

    if shortages:
        material = max(shortages.items(), key=lambda kv: kv[1])[0]
        quantity = max(30.0, shortages[material] * 1.2)
        return ConstructionAction(
            action_type="order_material",
            material_type=material,
            quantity=quantity,
        )

    return None


def _reschedule_ready_tasks(obs: Any) -> Optional[ConstructionAction]:
    tasks = _tasks_by_id(obs)
    candidates = []

    for t in obs.tasks:
        if t.progress >= 1.0:
            continue
        if obs.day >= t.planned_start_day:
            continue
        if not _deps_complete(t, tasks):
            continue

        urgency = 0
        if t.priority == "critical":
            urgency += 100
        elif t.priority == "high":
            urgency += 70
        urgency += max(0, t.days_behind_schedule) * 30
        candidates.append((urgency, t))

    if candidates:
        candidates.sort(reverse=True, key=lambda x: x[0])
        target = candidates[0][1]
        return ConstructionAction(
            action_type="reschedule_task",
            task_id=target.task_id,
            new_start_day=obs.day,
        )

    return None


def smart_policy(obs: Any) -> ConstructionAction:
    material_action = _handle_just_in_time_materials(obs)
    if material_action is not None:
        return material_action

    prefetch_action = _prefetch_near_unlock_materials(obs)
    if prefetch_action is not None:
        return prefetch_action

    reschedule_action = _reschedule_ready_tasks(obs)
    if reschedule_action is not None:
        return reschedule_action

    if obs.overtime_fatigue_level < 0.25:
        tasks = _ready_tasks(obs)
        if tasks:
            tasks.sort(key=_task_score, reverse=True)
            top = tasks[0]
            if top.is_critical_path and top.days_behind_schedule >= 2:
                return ConstructionAction(
                    action_type="approve_overtime",
                    task_id=top.task_id,
                    overtime_hours=2,
                )

    allocations = _compute_batch_allocations(obs)
    if allocations:
        return ConstructionAction(
            action_type="allocate_workers_batch",
            allocations=allocations,
        )

    if obs.workers_available > 0:
        return ConstructionAction(action_type="allocate_workers")

    if len(obs.active_issues or []) > 2:
        return ConstructionAction(
            action_type="request_pm_guidance",
            message="No executable tasks available; multiple issues detected",
        )

    return ConstructionAction(action_type="do_nothing")
