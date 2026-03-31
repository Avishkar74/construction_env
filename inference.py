"""
Inference runner for construction_env.

Submission requirements addressed:
- File name is `inference.py` at repository root.
- Uses OpenAI client for all LLM calls.
- Reads required env vars: API_BASE_URL, MODEL_NAME, HF_TOKEN.

Optional env vars:
- ENV_BASE_URL (default: https://avishkar-00-construction-env.hf.space)
- DIFFICULTY (default: medium)
- MAX_STEPS (default: 60)
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from openai import OpenAI

from client import ConstructionEnv
from models import ConstructionAction
from policies.strategy_v7 import reset_policy_state as reset_policy_state_v7
from policies.strategy_v7 import smart_policy as smart_policy_v7


API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3.2-Exp")
HF_TOKEN = os.getenv("HF_TOKEN")

ENV_BASE_URL = os.getenv("ENV_BASE_URL", "https://avishkar-00-construction-env.hf.space")
DIFFICULTY = os.getenv("DIFFICULTY", "medium")
MAX_STEPS = int(os.getenv("MAX_STEPS", "180"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "180"))
USE_POLICY = os.getenv("USE_POLICY", "false").lower() in ("1", "true", "yes")
STRATEGY_VERSION = os.getenv("STRATEGY_VERSION", "v7").lower()
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "outputs/inference_run.txt")
DEBUG_STEPS = os.getenv("DEBUG_STEPS", "0").lower() in ("1", "true", "yes")


def _fallback_action(obs: Any) -> ConstructionAction:
    """Safe deterministic fallback if model output is invalid."""
    for t in obs.tasks:
        if (not t.blocked) and t.progress < 1.0:
            need = max(1, t.required_workers - t.assigned_workers)
            wc = min(max(1, obs.workers_available), need)
            return ConstructionAction(
                action_type="allocate_workers",
                task_id=t.task_id,
                worker_count=wc,
            )
    return ConstructionAction(action_type="do_nothing")


def _observation_to_prompt(obs: Any) -> str:
    task_rows = []
    for t in obs.tasks[:12]:
        task_rows.append(
            f"id={t.task_id},status={t.status},progress={t.progress:.2f},"
            f"blocked={t.blocked},assigned={t.assigned_workers}/{t.required_workers},"
            f"behind={t.days_behind_schedule},priority={t.priority}"
        )

    return (
        "You are a construction project RL planner. Choose exactly ONE next action.\n"
        "Return ONLY compact JSON with keys from: "
        "action_type, task_id, worker_count, material_type, quantity, overtime_hours, new_start_day, message.\n"
        "Allowed action_type values: allocate_workers, order_material, approve_overtime, "
        "reschedule_task, do_nothing, request_pm_guidance.\n"
        "Prefer allocating workers to unfinished unblocked critical/high priority tasks.\n\n"
        f"day={obs.day}, max_days={obs.max_days}, weather={obs.weather}, "
        f"workers_available={obs.workers_available}, budget_used={obs.budget_used:.3f}\n"
        f"active_issues={obs.active_issues}\n"
        "tasks:\n- " + "\n- ".join(task_rows)
    )


def _parse_action(raw: str, obs: Any) -> ConstructionAction:
    raw = (raw or "").strip()
    try:
        payload: Dict[str, Any] = json.loads(raw)
        if "action_type" not in payload:
            return _fallback_action(obs)
        return ConstructionAction(**payload)
    except Exception:
        return _fallback_action(obs)


def _choose_action(client: OpenAI, obs: Any) -> ConstructionAction:
    user_prompt = _observation_to_prompt(obs)
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Respond with JSON only. No markdown, no explanation. "
                        "If uncertain, pick do_nothing."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
    except Exception:
        return _fallback_action(obs)

    text = response.choices[0].message.content or ""
    return _parse_action(text, obs)


def _get_strategy_fns():
    return reset_policy_state_v7, smart_policy_v7


def main() -> None:
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN is required")

    llm_client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

    reset_policy_state, smart_policy = _get_strategy_fns()
    if USE_POLICY:
        reset_policy_state()

    cumulative_reward = 0.0
    steps = 0
    action_counts = {
        "allocate_workers": 0,
        "allocate_workers_batch": 0,
        "multi_action": 0,
        "order_material": 0,
        "reschedule_task": 0,
        "approve_overtime": 0,
        "request_pm_guidance": 0,
        "do_nothing": 0,
        "other": 0,
    }
    zero_progress_steps = 0
    reward_component_totals: dict[str, float] = {}
    steps_with_reward_components = 0

    os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
    output_file = open(OUTPUT_PATH, "w", encoding="utf-8")

    def _write(line: str) -> None:
        print(line)
        output_file.write(line + "\n")

    with ConstructionEnv(base_url=ENV_BASE_URL).sync() as env:
        result = env.reset(difficulty=DIFFICULTY)

        while (not result.done) and steps < MAX_STEPS:
            obs = result.observation
            progress_before = sum(float(t.progress) for t in obs.tasks)
            if USE_POLICY:
                action = smart_policy(obs)
            else:
                action = _choose_action(llm_client, obs)
            action_type = action.action_type if action.action_type in action_counts else "other"
            action_counts[action_type] += 1
            result = env.step(action)
            reward = result.reward or 0.0
            cumulative_reward += reward
            reward_components = result.observation.reward_components or {}

            if DEBUG_STEPS:
                allocations_count = len(action.allocations or []) if hasattr(action, "allocations") else 0
                progress_after = sum(float(t.progress) for t in result.observation.tasks)
                progress_delta = progress_after - progress_before
                line = (
                    f"Day {result.observation.day:2d} | {action.action_type:22s} | "
                    f"task_id={action.task_id} | allocations={allocations_count} | "
                    f"workers={result.observation.workers_available}/{result.observation.total_workers} | "
                    f"delta={progress_delta:.3f}"
                )
                _write(line)

            if reward_components:
                steps_with_reward_components += 1
            for name, value in reward_components.items():
                if isinstance(value, (int, float)):
                    reward_component_totals[name] = reward_component_totals.get(name, 0.0) + float(value)

            if "progress" in reward_components:
                if float(reward_components.get("progress", 0.0)) <= 0.0:
                    zero_progress_steps += 1
            else:
                progress_after = sum(float(t.progress) for t in result.observation.tasks)
                if progress_after <= progress_before:
                    zero_progress_steps += 1
            steps += 1

        final_obs = result.observation
        total_tasks = len(final_obs.tasks)
        completed_tasks = sum(1 for t in final_obs.tasks if t.progress >= 1.0 or t.status == "completed")
        completion_score = (completed_tasks / total_tasks) if total_tasks else 0.0

    summary = {
        "difficulty": DIFFICULTY,
        "steps": steps,
        "done": bool(result.done),
        "cumulative_reward": round(cumulative_reward, 4),
        "completed_tasks": completed_tasks,
        "total_tasks": total_tasks,
        "score": round(completion_score, 4),
        "score_range_check": 0.0 <= completion_score <= 1.0,
        "use_policy": USE_POLICY,
        "strategy_version": STRATEGY_VERSION,
        "action_counts": action_counts,
        "zero_progress_steps": zero_progress_steps,
        "steps_with_reward_components": steps_with_reward_components,
        "reward_components_available": steps_with_reward_components > 0,
        "reward_component_totals": {k: round(v, 4) for k, v in sorted(reward_component_totals.items())},
        "reward_component_avg_per_step": {
            k: round((v / max(1, steps)), 4) for k, v in sorted(reward_component_totals.items())
        },
    }

    summary["iron_triangle"] = {
        "time_performance": {
            "zero_progress_days": zero_progress_steps,
            "completion_score": round(completion_score, 4),
            "finished_within_budget_days": bool(result.done and steps < MAX_STEPS),
        },
        "cost_performance": {
            "idle_waste_total": round(reward_component_totals.get("idle_penalty", 0.0), 4),
            "budget_pressure_total": round(reward_component_totals.get("budget_pressure", 0.0), 4),
            "bad_action_penalties": round(reward_component_totals.get("bad_action", 0.0), 4),
        },
        "quality_performance": {
            "delay_penalty_total": round(reward_component_totals.get("delay_penalty", 0.0), 4),
            "weather_penalty_total": round(reward_component_totals.get("weather_penalty", 0.0), 4),
            "efficiency_earned": round(reward_component_totals.get("efficiency", 0.0), 4),
        },
    }

    _write(json.dumps(summary, indent=2))
    output_file.close()


if __name__ == "__main__":
    main()
