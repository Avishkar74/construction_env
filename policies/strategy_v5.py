from __future__ import annotations
from typing import Any, Optional
from models import ConstructionAction

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
        ready.append(t)
    return ready

def _get_pending_quantity(obs: Any, material: str) -> float:
    qty = 0.0
    for order in (obs.pending_orders or []):
        mat = order.get("material_type") if isinstance(order, dict) else order.material_type
        amount = float(order.get("quantity", 0.0) if isinstance(order, dict) else order.quantity)
        if mat == material:
            qty += amount
    return qty

def _handle_just_in_time_materials(obs: Any) -> Optional[ConstructionAction]:
    # FAIR PLAY: Look ONLY at currently unlocked/ready tasks.
    ready = _ready_tasks(obs)
    
    shortages = {}
    for task in ready:
        remaining_progress = 1.0 - task.progress
        for mat, amt_per_10pct in (task.required_materials or {}).items():
            # Only order what this specific active task needs to cross the finish line
            needed_to_finish = amt_per_10pct * (remaining_progress * 10.0)
            have = (obs.materials_available or {}).get(mat, 0.0)
            pending = _get_pending_quantity(obs, mat)
            
            if have + pending < needed_to_finish:
                shortages[mat] = shortages.get(mat, 0.0) + (needed_to_finish - (have + pending))
                
    if shortages:
        # Order the most critical deficit just in time
        mat = max(shortages.items(), key=lambda x: x[1])[0]
        # Order realistic batches (e.g. at least 30) instead of raw 100% project hoarding
        amount_to_order = max(30.0, shortages[mat] * 1.1) 
        return ConstructionAction(
            action_type="order_material",
            material_type=mat,
            quantity=amount_to_order
        )
    return None

def _score_task(task: Any, obs: Any) -> float:
    score = 0.0
    if task.priority == "critical": score += 100
    elif task.priority == "high": score += 50
    score += task.progress * 150 # Stickiness
    
    # Value tasks that unlock other tasks
    for other in obs.tasks:
        if task.task_id in other.dependencies:
            score += 15
            
    return score

def smart_policy(obs: Any) -> ConstructionAction:
    global CURRENT_TASK_ID
    
    # 1) Realistic Just-In-Time Supply Chain
    mat_action = _handle_just_in_time_materials(obs)
    if mat_action:
        return mat_action
        
    # 2) Realistic Worker Allocation
    ready = [t for t in _ready_tasks(obs) if _has_min_materials(t, obs)]
    if ready:
        target = None
        # Stick to current task if it's still workable
        if CURRENT_TASK_ID is not None:
            for t in ready:
                if t.task_id == CURRENT_TASK_ID:
                    target = t
                    break
        
        # Select best new task
        if target is None:
            target = max(ready, key=lambda t: _score_task(t, obs))
            CURRENT_TASK_ID = target.task_id
            
        # FAIR PLAY: Cap at required_workers (No over-allocating infinite workforce exploits)
        allocation = min(target.required_workers or target.assigned_workers or 5, obs.workers_available)
        
        # Realistically try to catch up with overtime if falling behind
        if target.days_behind_schedule > 1 and obs.overtime_fatigue_level < 0.25:
            return ConstructionAction(
                action_type="approve_overtime",
                task_id=target.task_id,
                overtime_hours=2
            )
            
        return ConstructionAction(
            action_type="allocate_workers",
            task_id=target.task_id,
            worker_count=allocation
        )
        
    return ConstructionAction(action_type="do_nothing")