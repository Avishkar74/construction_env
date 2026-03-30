"""
Local Ollama-based inference runner for construction_env.

Usage:
- Set `OLLAMA_URL` (default: http://localhost:11434) to your local Ollama server.
- Set `OLLAMA_MODEL` to one of: "llama3.2:3b" or "qwen2.5:7b" (default: llama3.2:3b).
- Run: `python olamainference.py` (install `requests` if needed).
"""

from __future__ import annotations

import json
import os

from client import ConstructionEnv
from policies.strategy import reset_policy_state as reset_policy_state_v1
from policies.strategy import smart_policy as smart_policy_v1
from policies.strategy_v2 import reset_policy_state as reset_policy_state_v2
from policies.strategy_v2 import smart_policy as smart_policy_v2
from policies.strategy_v2_1 import reset_policy_state as reset_policy_state_v2_1
from policies.strategy_v2_1 import smart_policy as smart_policy_v2_1
from policies.strategy_v3 import reset_policy_state as reset_policy_state_v3
from policies.strategy_v3 import smart_policy as smart_policy_v3
from policies.strategy_v4 import reset_policy_state as reset_policy_state_v4
from policies.strategy_v4 import smart_policy as smart_policy_v4
from policies.strategy_v5 import reset_policy_state as reset_policy_state_v5
from policies.strategy_v5 import smart_policy as smart_policy_v5
from policies.strategy_v6 import reset_policy_state as reset_policy_state_v6
from policies.strategy_v6 import smart_policy as smart_policy_v6
from policies.strategy_v7 import reset_policy_state as reset_policy_state_v7
from policies.strategy_v7 import smart_policy as smart_policy_v7
from policies.strategy_scheduler_test import reset_policy_state as reset_policy_state_sched
from policies.strategy_scheduler_test import smart_policy as smart_policy_sched
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
DIFFICULTY = os.getenv("DIFFICULTY", "medium")
MAX_STEPS = int(os.getenv("MAX_STEPS", "60"))
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")
STRATEGY_VERSION = os.getenv("STRATEGY_VERSION", "v7").lower()
DEBUG_STEPS = os.getenv("DEBUG_STEPS", "0").lower() in ("0", "true", "yes")


def _get_strategy_fns():
    if STRATEGY_VERSION == "v1":
        return reset_policy_state_v1, smart_policy_v1
    if STRATEGY_VERSION in ("v2.1", "v2_1"):
        return reset_policy_state_v2_1, smart_policy_v2_1
    if STRATEGY_VERSION == "v5":
        return reset_policy_state_v5, smart_policy_v5
    if STRATEGY_VERSION == "v6":
        return reset_policy_state_v6, smart_policy_v6
    if STRATEGY_VERSION == "v7":
        return reset_policy_state_v7, smart_policy_v7
    if STRATEGY_VERSION in ("sched", "scheduler", "scheduler_test"):
        return reset_policy_state_sched, smart_policy_sched
    if STRATEGY_VERSION == "v4":
        return reset_policy_state_v4, smart_policy_v4
    if STRATEGY_VERSION == "v3":
        return reset_policy_state_v3, smart_policy_v3
    return reset_policy_state_v2, smart_policy_v2


def main() -> None:
    reset_policy_state, smart_policy = _get_strategy_fns()
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

    with ConstructionEnv(base_url=ENV_BASE_URL).sync() as env:
        result = env.reset(difficulty=DIFFICULTY)

        while (not result.done) and steps < MAX_STEPS:
            obs = result.observation
            progress_before = sum(float(t.progress) for t in obs.tasks)
            action = smart_policy(obs)
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
                print(line)
                if action.action_type == "multi_action" and action.actions:
                    for sub in action.actions:
                        sub_allocs = len(sub.allocations or []) if hasattr(sub, "allocations") else 0
                        print(
                            f"  - {sub.action_type} | task_id={sub.task_id} | "
                            f"allocations={sub_allocs} | qty={sub.quantity} | start={sub.new_start_day}"
                        )
            if reward_components:
                steps_with_reward_components += 1
            for name, value in reward_components.items():
                if isinstance(value, (int, float)):
                    reward_component_totals[name] = reward_component_totals.get(name, 0.0) + float(value)
            # Prefer reward-components progress when available; otherwise infer from task progress delta.
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
        "ollama_model": OLLAMA_MODEL,
        "ollama_url": OLLAMA_URL,
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

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
