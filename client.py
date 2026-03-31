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
            max_days=obs_data.get("max_days", 180),
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
            reward_components=obs_data.get("reward_components"),
            equipment_health=obs_data.get("equipment_health", {}),
            critical_path_tasks=obs_data.get("critical_path_tasks", []),
            days_remaining=obs_data.get("days_remaining", 0),
            overall_progress=obs_data.get("overall_progress", 0.0),
            idle_workers_ratio=obs_data.get("idle_workers_ratio", 0.0),
            overtime_hours=obs_data.get("overtime_hours", 0.0),
            material_waste=obs_data.get("material_waste", 0.0),
            delay_penalty=obs_data.get("delay_penalty", 0.0),
            cement_quality=obs_data.get("cement_quality", 1.0),
            available_actions=obs_data.get("available_actions", []),
            completed_actions=obs_data.get("completed_actions", []),
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
            max_days=payload.get("max_days", 180),
            true_task_progress=payload.get("true_task_progress", {}),
            worker_efficiency=payload.get("worker_efficiency", 1.0),
            overtime_fatigue=payload.get("overtime_fatigue", 0.0),
            pending_orders=payload.get("pending_orders", []),
            upcoming_disruptions=payload.get("upcoming_disruptions", []),
            equipment_health=payload.get("equipment_health", {"crane": 1.0, "excavator": 1.0}),
            total_budget=payload.get("total_budget", 500_000.0),
            total_cost=payload.get("total_cost", 0.0),
            total_delay_days=payload.get("total_delay_days", 0),
            last_action_count=payload.get("last_action_count", 0),
            last_overtime_hours=payload.get("last_overtime_hours", 0.0),
            last_material_waste=payload.get("last_material_waste", 0.0),
            cumulative_overtime_hours=payload.get("cumulative_overtime_hours", 0.0),
            cumulative_idle_workers=payload.get("cumulative_idle_workers", 0),
            cumulative_material_waste=payload.get("cumulative_material_waste", 0.0),
            cumulative_action_count=payload.get("cumulative_action_count", 0),
            cumulative_multi_action_count=payload.get("cumulative_multi_action_count", 0),
            cumulative_bad_action_count=payload.get("cumulative_bad_action_count", 0),
            cumulative_zero_progress_days=payload.get("cumulative_zero_progress_days", 0),
            current_weather=payload.get("current_weather", "clear"),
            active_issues=payload.get("active_issues", []),
            completed_actions=payload.get("completed_actions", []),
            quality_inspection_days=payload.get("quality_inspection_days", 0),
            equipment_booking_days=payload.get("equipment_booking_days", 0),
            replan_bonus_days=payload.get("replan_bonus_days", 0),
            weather_mitigation_days=payload.get("weather_mitigation_days", 0),
        )