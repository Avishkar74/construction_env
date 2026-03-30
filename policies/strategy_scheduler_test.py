from __future__ import annotations

from typing import Any

from models import ConstructionAction


def reset_policy_state() -> None:
    return None


def smart_policy(obs: Any) -> ConstructionAction:
    # Intentionally omit task_id to force environment-side dynamic scheduling.
    return ConstructionAction(action_type="allocate_workers")
