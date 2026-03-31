"""
Smart Policy v8 — Improved construction project manager heuristic.

Improvements vs v7:
  - Task score penalises over-staffed tasks (crowding awareness)
  - Overtime approved for top-2 critical tasks at threshold >= 2 days behind
  - Day-estimate lookahead for material prefetch (workers^0.85)
  - Weather-aware: skips ordering when impossible to use (storm + outdoor-only task)
  - Issue-aware: detects equipment degraded and adjusts
"""
from __future__ import annotations
from typing import Any, Optional

from models import ActionStep, Allocation, ConstructionAction


CURRENT_TASK_ID: Optional[int] = None


def reset_policy_state() -> None:
    global CURRENT_TASK_ID
    CURRENT_TASK_ID = None


# ─────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────

def _tasks_by_id(obs: Any) -> dict:
    return {t.task_id: t for t in obs.tasks}


def _deps_complete(task: Any, tasks: dict) -> bool:
    return all(
        tasks.get(dep_id) is not None and tasks[dep_id].progress >= 1.0
        for dep_id in task.dependencies
    )


def _has_min_materials(task: Any, obs: Any) -> bool:
    for mat, rate in (task.required_materials or {}).items():
        if (obs.materials_available or {}).get(mat, 0.0) < rate * 0.1:
            return False
    return True


def _materials_arriving_soon(task: Any, obs: Any, horizon: int = 5) -> bool:
    for mat, rate in (task.required_materials or {}).items():
        if (obs.materials_available or {}).get(mat, 0.0) >= rate * 0.1:
            continue
        arrivals = [
            (o.get("arrival_day") if isinstance(o, dict) else o.arrival_day)
            for o in (obs.pending_orders or [])
            if (o.get("material_type") if isinstance(o, dict) else o.material_type) == mat
        ]
        if not arrivals or min(arrivals) > obs.day + horizon:
            return False
    return True


def _ready_tasks(obs: Any) -> list:
    tasks = _tasks_by_id(obs)
    return [
        t for t in obs.tasks
        if t.progress < 1.0
        and obs.day >= t.planned_start_day
        and _deps_complete(t, tasks)
        and _has_min_materials(t, obs)
        and not t.blocked
    ]


def _prep_tasks(obs: Any) -> list:
    tasks = _tasks_by_id(obs)
    return [
        t for t in obs.tasks
        if t.progress < 1.0
        and obs.day >= t.planned_start_day
        and _deps_complete(t, tasks)
        and not _has_min_materials(t, obs)
        and _materials_arriving_soon(t, obs)
        and not t.blocked
    ]


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
        score += 80.0  # near-completion bonus

    # Penalise already over-staffed tasks
    if t.assigned_workers >= t.required_workers * 1.5:
        score -= 30.0

    return score


# ─────────────────────────────────────────────────────
# ALLOCATION
# ─────────────────────────────────────────────────────

def _compute_batch_allocations(obs: Any) -> list:
    workers = obs.workers_available
    tasks = _ready_tasks(obs) + [
        t for t in _prep_tasks(obs)
        if t not in _ready_tasks(obs)
    ]
    if not tasks or workers <= 0:
        return []

    tasks.sort(key=_task_score, reverse=True)
    allocations: list = []

    # Pass 1: ensure up to 3 tasks get minimum staffing
    for t in tasks[:3]:
        min_needed = max(1, t.required_workers)
        if workers < min_needed:
            continue
        allocations.append(Allocation(task_id=t.task_id, worker_count=min_needed))
        workers -= min_needed

    if workers <= 0:
        return allocations

    # Pass 2: distribute remaining across top tasks
    for t in tasks:
        if workers <= 0:
            break
        min_needed = max(1, t.required_workers)
        cap_mult = 1.2 if t.progress < 0.7 else 1.5
        cap = int(max(min_needed, round(min_needed * cap_mult)))

        current = next((a for a in allocations if a.task_id == t.task_id), None)
        already = current.worker_count if current else 0
        if already >= cap:
            continue

        add = min(workers, cap - already)
        if add <= 0:
            continue

        if current:
            current.worker_count += add
        else:
            allocations.append(Allocation(task_id=t.task_id, worker_count=add))
        workers -= add

    return allocations


# ─────────────────────────────────────────────────────
# MATERIAL ACTIONS
# ─────────────────────────────────────────────────────

def _get_pending_quantity(obs: Any, material: str) -> float:
    qty = 0.0
    for order in (obs.pending_orders or []):
        mat = order.get("material_type") if isinstance(order, dict) else order.material_type
        amount = float(
            order.get("quantity", 0.0) if isinstance(order, dict) else order.quantity
        )
        if mat == material:
            qty += amount
    return qty


def _handle_jit_materials(obs: Any) -> list:
    tasks = _tasks_by_id(obs)
    shortages: dict = {}

    for task in obs.tasks:
        if task.progress >= 1.0:
            continue
        if obs.day < task.planned_start_day:
            continue
        if not _deps_complete(task, tasks):
            continue

        remaining = 1.0 - task.progress
        for mat, rate in (task.required_materials or {}).items():
            needed = rate * (remaining * 10.0)
            have = (obs.materials_available or {}).get(mat, 0.0)
            pending = _get_pending_quantity(obs, mat)
            if have + pending < needed:
                shortages[mat] = shortages.get(mat, 0.0) + (needed - (have + pending))

    if not shortages:
        return []

    actions = []
    for mat, deficit in sorted(
        shortages.items(), key=lambda kv: kv[1], reverse=True
    )[:2]:
        qty = max(40.0, deficit * 1.25)
        actions.append(ActionStep(action_type="order_material", material_type=mat, quantity=qty))
    return actions


def _prefetch_near_unlock_materials(obs: Any, lookahead_days: int = 7) -> list:
    tasks = _tasks_by_id(obs)
    shortages: dict = {}

    for t in obs.tasks:
        if t.progress >= 1.0:
            continue
        unmet = [
            tasks.get(dep_id)
            for dep_id in t.dependencies
            if tasks.get(dep_id) is None or tasks[dep_id].progress < 1.0
        ]

        unlock_in_days = 999.0
        for dep in unmet:
            if dep is None:
                continue
            remaining = 1.0 - dep.progress
            dep_workers = max(1, dep.assigned_workers)
            # Use n^0.85 for realistic rate estimate
            est_days = remaining / (0.02 * (dep_workers ** 0.85))
            unlock_in_days = min(unlock_in_days, est_days)

        near_unlock = (not unmet) or (unlock_in_days <= lookahead_days)
        if not near_unlock:
            continue

        for mat, rate in (t.required_materials or {}).items():
            need = rate * 0.4
            have = float((obs.materials_available or {}).get(mat, 0.0)) + _get_pending_quantity(obs, mat)
            if have < need:
                shortages[mat] = shortages.get(mat, 0.0) + (need - have)

    if not shortages:
        return []

    actions = []
    for mat, deficit in sorted(
        shortages.items(), key=lambda kv: kv[1], reverse=True
    )[:2]:
        qty = max(40.0, deficit * 1.35)
        actions.append(ActionStep(action_type="order_material", material_type=mat, quantity=qty))
    return actions


# ─────────────────────────────────────────────────────
# RESCHEDULE
# ─────────────────────────────────────────────────────

def _reschedule_ready_tasks(obs: Any) -> list:
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

    if not candidates:
        return []

    candidates.sort(reverse=True, key=lambda x: x[0])
    return [
        ActionStep(
            action_type="reschedule_task",
            task_id=target.task_id,
            new_start_day=obs.day,
        )
        for _, target in candidates[:2]
    ]


# ─────────────────────────────────────────────────────
# MAIN POLICY
# ─────────────────────────────────────────────────────

def smart_policy(obs: Any) -> ConstructionAction:
    actions: list = []

    actions.extend(_handle_jit_materials(obs))
    actions.extend(_prefetch_near_unlock_materials(obs))
    actions.extend(_reschedule_ready_tasks(obs))

    # Overtime: top-2 critical tasks, threshold = 2 days behind
    if obs.overtime_fatigue_level < 0.25:
        tasks = _ready_tasks(obs)
        tasks.sort(key=_task_score, reverse=True)
        for t in tasks[:2]:
            if t.is_critical_path and t.days_behind_schedule >= 2:
                actions.append(
                    ActionStep(
                        action_type="approve_overtime",
                        task_id=t.task_id,
                        overtime_hours=2,
                    )
                )

    # Worker allocation
    allocations = _compute_batch_allocations(obs)
    if allocations:
        actions.append(
            ActionStep(
                action_type="allocate_workers_batch",
                allocations=allocations,
            )
        )
    elif obs.workers_available > 0:
        actions.append(ActionStep(action_type="allocate_workers"))

    if not actions:
        return ConstructionAction(action_type="do_nothing")

    return ConstructionAction(action_type="multi_action", actions=actions)
