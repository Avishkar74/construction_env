# client.py
"""
Remote client for ConstructionEnvironment.
Install:  pip install git+https://huggingface.co/spaces/<your-username>/construction-env
Usage:
    from construction_env import ConstructionEnv, ConstructionAction

    with ConstructionEnv(base_url="https://<username>-construction-env.hf.space").sync() as env:
        obs = env.reset(difficulty="medium")
        while not obs.done:
            action = ConstructionAction(action_type="do_nothing")
            obs = env.step(action)
        print("Final score:", obs.reward)
"""

from openenv.core.env_client import EnvClient
from openenv.core.client_types import StepResult

from models import (
    ConstructionAction,
    ConstructionObservation,
    ConstructionState,
    TaskObservation,
)


class ConstructionEnv(EnvClient[ConstructionAction, ConstructionObservation, ConstructionState]):

    def _step_payload(self, action: ConstructionAction) -> dict:
        return action.model_dump(exclude_none=True)

    def _parse_result(self, payload: dict) -> StepResult:
        obs_data = payload.get("observation", payload)  # handle both wrapped and flat

        # Reward/done may be provided at the top-level (HTTP StepResponse)
        # or inside the observation dict depending on server wiring. Prefer
        # the top-level payload values and fall back to observation.
        reward_val = payload.get("reward", obs_data.get("reward"))
        done_val = payload.get("done", obs_data.get("done", False))

        # Parse tasks list
        tasks = [
            TaskObservation(**t)
            for t in obs_data.get("tasks", [])
        ]

        obs = ConstructionObservation(
            done=done_val,
            reward=reward_val,
            day=obs_data.get("day", 1),
            max_days=obs_data.get("max_days", 60),
            tasks=tasks,
            workers_available=obs_data.get("workers_available", 0),
            total_workers=obs_data.get("total_workers", 20),
            overtime_fatigue_level=obs_data.get("overtime_fatigue_level", 0.0),
            materials_available=obs_data.get("materials_available", {}),
            pending_orders=obs_data.get("pending_orders", []),
            weather=obs_data.get("weather", "clear"),
            active_issues=obs_data.get("active_issues", []),
            budget_total=obs_data.get("budget_total", 0.0),
            budget_used=obs_data.get("budget_used", 0.0),
            chat_messages=obs_data.get("chat_messages", []),
            difficulty=obs_data.get("difficulty", "medium"),
        )

        return StepResult(
            observation=obs,
            reward=reward_val,
            done=done_val,
        )

    def _parse_state(self, payload: dict) -> ConstructionState:
        return ConstructionState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            current_day=payload.get("current_day", 1),
            difficulty=payload.get("difficulty", "medium"),
            max_days=payload.get("max_days", 60),
            true_task_progress=payload.get("true_task_progress", {}),
            worker_efficiency=payload.get("worker_efficiency", 1.0),
            overtime_fatigue=payload.get("overtime_fatigue", 0.0),
            total_budget=payload.get("total_budget", 500_000.0),
            total_cost=payload.get("total_cost", 0.0),
            total_delay_days=payload.get("total_delay_days", 0),
            current_weather=payload.get("current_weather", "clear"),
        )