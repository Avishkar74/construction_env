from __future__ import annotations
from typing import Any, Optional
from models import ConstructionAction

CURRENT_TASK_ID: Optional[int] = None
ORDERED_MATERIALS: set[str] = set()

def reset_policy_state() -> None:
    global CURRENT_TASK_ID, ORDERED_MATERIALS
    CURRENT_TASK_ID = None
    ORDERED_MATERIALS.clear()

def _calculate_total_material_needs(obs: Any) -> dict[str, float]:
    needs: dict[str, float] = {}
    for task in obs.tasks:
        for mat, amt_per_10pct in (task.required_materials or {}).items():
            # Amount needed for 100% progress
            needs[mat] = needs.get(mat, 0.0) + (amt_per_10pct * 10.0)
    return needs

def _get_current_and_pending_materials(obs: Any) -> dict[str, float]:
    available = dict(obs.materials_available) if obs.materials_available else {}
    for order in (obs.pending_orders or []):
        mat = order.get("material_type") if isinstance(order, dict) else order.material_type
        qty = float(order.get("quantity", 0.0) if isinstance(order, dict) else order.quantity)
        available[mat] = available.get(mat, 0.0) + qty
    return available

def _handle_global_materials(obs: Any) -> Optional[ConstructionAction]:
    needs = _calculate_total_material_needs(obs)
    have = _get_current_and_pending_materials(obs)
    
    for mat, total_needed in needs.items():
        current_have = have.get(mat, 0.0)
        # Order buffer of 5% just in case of rounding errors
        if current_have < total_needed * 1.05 and mat not in ORDERED_MATERIALS:
            deficit = (total_needed * 1.05) - current_have
            ORDERED_MATERIALS.add(mat)
            return ConstructionAction(
                action_type="order_material",
                material_type=mat,
                quantity=max(50.0, deficit)
            )
    return None

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
        ready.append(t)
    return ready

def _score_task(task: Any, obs: Any) -> float:
    score = 0.0
    if task.priority == "critical": score += 100
    elif task.priority == "high": score += 50
    score += task.progress * 200 # Heavily bias towards finishing current task
    
    # dependencies this task unlocks
    for other in obs.tasks:
        if task.task_id in other.dependencies:
            score += 10
            if other.is_critical_path:
                score += 30
    
    return score

def _select_task(obs: Any) -> Optional[Any]:
    ready = _ready_tasks(obs)
    if not ready:
        return None
        
    global CURRENT_TASK_ID
    # Stick to current task if it's still valid
    if CURRENT_TASK_ID is not None:
        for t in ready:
            if t.task_id == CURRENT_TASK_ID:
                return t
                
    # Otherwise find best
    target = max(ready, key=lambda t: _score_task(t, obs))
    CURRENT_TASK_ID = target.task_id
    return target

def smart_policy(obs: Any) -> ConstructionAction:
    global CURRENT_TASK_ID
    
    # 1) PRE-ORDER ALL MATERIALS FOR THE ENTIRE PROJECT
    mat_action = _handle_global_materials(obs)
    if mat_action:
        return mat_action

    # 2) SWARM THE MOST CRITICAL READY TASK
    task = _select_task(obs)
    if task is not None:
        # Never overtime, it drags efficiency to 0.6. Stay at max efficiency by just taking normal day!
        return ConstructionAction(
            action_type="allocate_workers",
            task_id=task.task_id,
            worker_count=obs.total_workers,
        )

    # 3) Fallback
    return ConstructionAction(action_type="do_nothing")
