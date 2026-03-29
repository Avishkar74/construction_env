from __future__ import annotations

from typing import Any, Optional


def _priority_weight(priority: str) -> int:
    if priority == "critical":
        return 100
    if priority == "high":
        return 70
    if priority == "medium":
        return 40
    return 10


def get_best_ready_task(obs: Any, current_task_id: Optional[str] = None) -> Optional[Any]:
    # Keep focus on the same task if still actionable.
    if current_task_id is not None:
        for t in obs.tasks:
            if t.task_id == current_task_id and (not t.blocked) and t.progress < 1.0:
                return t

    ready_tasks = [t for t in obs.tasks if (not t.blocked) and t.progress < 1.0]
    if not ready_tasks:
        return None

    return max(
        ready_tasks,
        key=lambda t: (
            _priority_weight(t.priority)
            + max(0, t.days_behind_schedule) * 50
            + (1 if t.progress > 0.7 else 0) * 100
            + t.progress * 20
        ),
    )
