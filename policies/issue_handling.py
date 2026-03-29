from __future__ import annotations

from typing import Any, Optional

from models import ConstructionAction


def _task_index(obs: Any) -> dict[int, Any]:
    return {t.task_id: t for t in obs.tasks}


def _dependencies_complete(task: Any, tasks_by_id: dict[int, Any]) -> bool:
    for dep_id in task.dependencies:
        dep = tasks_by_id.get(dep_id)
        if dep is None or dep.progress < 1.0:
            return False
    return True


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


def handle_blocked_tasks(obs: Any) -> Optional[ConstructionAction]:
    tasks_by_id = _task_index(obs)

    # Reschedule only when dependencies are satisfied but planned start is in the future.
    # This avoids wasting steps trying to "reschedule away" dependency/material blockers.
    candidates = []
    for t in obs.tasks:
        if t.progress >= 1.0:
            continue
        if not _dependencies_complete(t, tasks_by_id):
            continue
        if obs.day < t.planned_start_day:
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


def handle_material_issue(obs: Any) -> Optional[ConstructionAction]:
    tasks_by_id = _task_index(obs)
    shortages: dict[str, float] = {}

    for t in obs.tasks:
        if t.progress >= 1.0:
            continue
        if not _dependencies_complete(t, tasks_by_id):
            continue
        for mat, amount_per_10pct in (t.required_materials or {}).items():
            # Minimum stock required to make any progress this step.
            needed_now = amount_per_10pct * 0.1
            have = float((obs.materials_available or {}).get(mat, 0.0))
            # Include near-term incoming orders to avoid over-ordering repeatedly.
            have += _pending_quantity(obs, mat, horizon_days=4)
            if have < needed_now:
                shortages[mat] = shortages.get(mat, 0.0) + (needed_now - have)

    if shortages:
        material = max(shortages.items(), key=lambda kv: kv[1])[0]
        deficit = shortages[material]
        # Favor fewer, larger orders to avoid spending too many days on logistics actions.
        quantity = min(400, max(80, int(deficit * 120)))
        return ConstructionAction(
            action_type="order_material",
            material_type=material,
            quantity=quantity,
        )

    return None


def maybe_ask_pm(obs: Any) -> Optional[ConstructionAction]:
    if len(obs.active_issues or []) > 2:
        return ConstructionAction(
            action_type="request_pm_guidance",
            message="No executable tasks available; multiple issues detected",
        )
    return None
