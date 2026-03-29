from __future__ import annotations

from typing import Any

from models import ConstructionAction


def allocate_all_workers(obs: Any, task: Any) -> ConstructionAction:
    return ConstructionAction(
        action_type="allocate_workers",
        task_id=task.task_id,
        worker_count=max(1, obs.workers_available),
    )
