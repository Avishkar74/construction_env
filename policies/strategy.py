from __future__ import annotations

from typing import Any, Optional

from models import ConstructionAction

from policies.issue_handling import handle_blocked_tasks, handle_material_issue, maybe_ask_pm
from policies.resource_allocation import allocate_all_workers
from policies.task_selection import get_best_ready_task


CURRENT_TASK_ID: Optional[str] = None


def reset_policy_state() -> None:
    global CURRENT_TASK_ID
    CURRENT_TASK_ID = None


def smart_policy(obs: Any) -> ConstructionAction:
    global CURRENT_TASK_ID

    # 1) Execute ready work first.
    task = get_best_ready_task(obs, current_task_id=CURRENT_TASK_ID)
    if task is not None:
        CURRENT_TASK_ID = task.task_id
        return allocate_all_workers(obs, task)

    # 2) Resolve material shortage if present.
    material_action = handle_material_issue(obs)
    if material_action is not None:
        return material_action

    # 3) If nothing executable, selectively reschedule future-start tasks.
    blocked_action = handle_blocked_tasks(obs)
    if blocked_action is not None:
        return blocked_action

    # 4) Escalate when system is broadly constrained.
    pm_action = maybe_ask_pm(obs)
    if pm_action is not None:
        return pm_action

    return ConstructionAction(action_type="do_nothing")
