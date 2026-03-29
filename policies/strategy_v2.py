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
        return 120
    if priority == "high":
        return 80
    if priority == "medium":
        return 40
    return 10


def _tasks_by_id(obs: Any) -> dict[int, Any]:
    return {t.task_id: t for t in obs.tasks}


def _deps_complete(task: Any, tasks: dict[int, Any]) -> bool:
    for dep_id in task.dependencies:
        dep = tasks.get(dep_id)
        if dep is None or dep.progress < 1.0:
            return False
    return True


def _ready_tasks(obs: Any) -> list[Any]:
    tasks = _tasks_by_id(obs)
    ready = []
    for t in obs.tasks:
        if t.progress >= 1.0 or t.blocked:
            continue
        if obs.day < t.planned_start_day:
            continue
        if not _deps_complete(t, tasks):
            continue
        ready.append(t)
    return ready


def _score_task(task: Any) -> float:
    score = 0.0
    score += _priority_weight(task.priority)
    score += max(0, task.days_behind_schedule) * 55
    score += 30.0 if task.is_critical_path else 0.0
    score += task.progress * 30.0
    if task.progress > 0.75:
        score += 90.0
    return score


def _select_task(obs: Any) -> Optional[Any]:
    global CURRENT_TASK_ID

    ready = _ready_tasks(obs)
    if not ready:
        return None

    # Task lock: continue current task if still ready.
    if CURRENT_TASK_ID is not None:
        for t in ready:
            if t.task_id == CURRENT_TASK_ID:
                return t

    return max(ready, key=_score_task)


def _maybe_overtime(obs: Any, task: Any) -> Optional[ConstructionAction]:
    behind = task.days_behind_schedule > 0
    important = task.priority in ("critical", "high") or task.is_critical_path
    enough_workers = obs.workers_available >= max(1, task.required_workers)
    fatigue_ok = obs.overtime_fatigue_level < 0.55

    if behind and important and enough_workers and fatigue_ok:
        return ConstructionAction(
            action_type="approve_overtime",
            task_id=task.task_id,
            overtime_hours=2,
        )
    return None


def smart_policy(obs: Any) -> ConstructionAction:
    global CURRENT_TASK_ID

    # 1) Execute ready work first with strong completion bias.
    task = _select_task(obs)
    if task is not None:
        CURRENT_TASK_ID = task.task_id
        overtime_action = _maybe_overtime(obs, task)
        if overtime_action is not None:
            return overtime_action
        return allocate_all_workers(obs, task)

    # 2) If no executable work, replenish materials for next actionable tasks.
    material_action = handle_material_issue(obs)
    if material_action is not None:
        return material_action

    # 3) Bring future-start tasks forward when dependencies are ready.
    reschedule_action = handle_blocked_tasks(obs)
    if reschedule_action is not None:
        return reschedule_action

    # 4) Escalate only when truly constrained.
    pm_action = maybe_ask_pm(obs)
    if pm_action is not None:
        return pm_action

    return ConstructionAction(action_type="do_nothing")
