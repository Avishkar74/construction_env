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


API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3.2-Exp")
HF_TOKEN = os.getenv("HF_TOKEN")

ENV_BASE_URL = os.getenv("ENV_BASE_URL", "https://avishkar-00-construction-env.hf.space")
DIFFICULTY = os.getenv("DIFFICULTY", "medium")
MAX_STEPS = int(os.getenv("MAX_STEPS", "60"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "180"))


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

    text = response.choices[0].message.content or ""
    return _parse_action(text, obs)


def main() -> None:
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN is required")

    llm_client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

    cumulative_reward = 0.0
    steps = 0

    with ConstructionEnv(base_url=ENV_BASE_URL).sync() as env:
        result = env.reset(difficulty=DIFFICULTY)

        while (not result.done) and steps < MAX_STEPS:
            obs = result.observation
            action = _choose_action(llm_client, obs)
            result = env.step(action)
            reward = result.reward or 0.0
            cumulative_reward += reward
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
    }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
