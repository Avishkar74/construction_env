"""
Inference runner for construction_env.

Environment variables:
  API_BASE_URL  — LLM endpoint (default: https://router.huggingface.co/v1)
  MODEL_NAME    — LLM model ID
  HF_TOKEN      — Hugging Face / API key (required)
  ENV_BASE_URL  — Environment server URL
  DIFFICULTY    — easy | medium | hard  (default: medium)
  MAX_STEPS     — max episode steps (default: 180)
    USE_POLICY    — unused (LLM-only)
  DEBUG_STEPS   — "true" to print per-step details
  OUTPUT_PATH   — path for summary JSON output
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from client import ConstructionEnv
from models import ConstructionAction, ConstructionState


API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3-0324")
HF_TOKEN = os.getenv("HF_TOKEN")

ENV_BASE_URL = os.getenv("ENV_BASE_URL", "https://avishkar-00-construction-env.hf.space")
DIFFICULTY = os.getenv("DIFFICULTY", "medium")
MAX_STEPS = int(os.getenv("MAX_STEPS", "180"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "200"))
USE_POLICY = False
DEBUG_STEPS = os.getenv("DEBUG_STEPS", "0").lower() in ("1", "true", "yes")
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "outputs/inference_run.txt")


# ─────────────────────────────────────────────────────
# LLM FALLBACK
# ─────────────────────────────────────────────────────

def _fallback_action(obs: Any) -> ConstructionAction:
    for t in obs.tasks:
        if (not t.blocked) and t.progress < 1.0:
            wc = min(max(1, obs.workers_available), max(1, t.required_workers))
            return ConstructionAction(
                action_type="allocate_workers",
                task_id=t.task_id,
                worker_count=wc,
            )
    return ConstructionAction(action_type="do_nothing")


def get_valid_task_ids(obs) -> list[int]:
    task_map = {t.task_id: t for t in obs.tasks}
    valid = []
    for task in obs.tasks:
        if task.status == "completed" or task.blocked:
            continue
        if obs.day < task.planned_start_day:
            continue
        deps_met = all(
            task_map.get(dep_id) is not None and task_map[dep_id].progress >= 1.0
            for dep_id in task.dependencies
        )
        mats_ok = all(
            (obs.materials_available or {}).get(mat, 0) >= rate * 0.1
            for mat, rate in (task.required_materials or {}).items()
        )
        if deps_met and mats_ok:
            valid.append(task.task_id)
    return valid


def _observation_to_prompt(obs: Any) -> str:
    task_rows = []
    for t in obs.tasks[:12]:
        task_rows.append(
            f"id={t.task_id},status={t.status},progress={t.progress:.2f},"
            f"blocked={t.blocked},assigned={t.assigned_workers}/{t.required_workers},"
            f"behind={t.days_behind_schedule},priority={t.priority}"
        )
    available = list(getattr(obs, "available_actions", []) or [])
    available_list = ", ".join(available) if available else ""
    return (
        "You are a construction project decision agent. Choose the single BEST next action.\n"
        "A multi_action is still ONE action; it just contains 2-5 sub-actions.\n"
        "Return ONLY compact JSON with keys from: action_type, task_id, worker_count, "
        "material_type, quantity, overtime_hours, new_start_day, message, actions.\n"
        "Allowed action_type values: choose ONLY from available_actions.\n\n"
        "Decision workflow (follow in order):\n"
        "1) Understand state: active tasks, blocked tasks, idle workers, material shortages, delays, and risks.\n"
        "2) Identify the SINGLE biggest bottleneck (blocked critical task, idle workers, material shortage, "
        "schedule delay, cost inefficiency, or no actionable task).\n"
        "3) Apply priority order strictly: unblock critical path > prevent near-future blocking > "
        "utilize idle workers > reduce delays > optimize cost > strategic improvements.\n"
        "4) Candidate evaluation: pick TOP 3 actions from available_actions (or all if fewer than 3).\n"
        "   For each candidate, judge: progress gain, delay reduction, idle worker utilization, cost impact, "
        "and next-2-3-step benefits.\n"
        "5) Choose the best action with highest overall benefit and lowest negative side effects.\n\n"
        "Category guidance (use as a mental map):\n"
        "- scheduling: create_schedule, reschedule_tasks, replan_project, handle_weather_delay\n"
        "- workforce: allocate_workers, reassign_workers, hire_workers, approve_overtime\n"
        "- material: order_material, schedule_equipment, book_equipment\n"
        "- quality: conduct_quality_inspection, conduct_cube_tests, fix_defect\n"
        "- risk: handle_weather_delay, request_pm_guidance\n"
        "- strategy: optimize_cost, approve_go_no_go\n"
        "- meta: request_pm_guidance, do_nothing\n\n"
        "Action selection rules:\n"
        "- Never pick actions outside available_actions.\n"
        "- Never assign workers to blocked tasks or ignore dependencies.\n"
        "- Choose do_nothing only when NO feasible or useful action exists today.\n"
        "- Never over-allocate workers beyond reasonable need for a task.\n"
        "- Prefer actions that create progress within the next 2-3 steps.\n"
        "- multi_action: use only when 2-5 complementary actions together beat any single action.\n"
        "  Every sub-action MUST be from available_actions and feasible today.\n"
        "VALIDATION RULES:\n"
        "- If choosing allocate_workers, task_id MUST be in valid_task_ids.\n"
        "- If choosing allocate_workers_batch, allocations MUST be non-empty and each task_id in valid_task_ids.\n\n"
        "If using multi_action, include 'actions' as a list of 1-5 action objects.\n"
        "If uncertain, choose request_pm_guidance and include a suggested action in message.\n\n"
        "OUTPUT FORMAT (strict JSON only):\n"
        "{\n"
        "  \"action_type\": \"allocate_workers\",\n"
        "  \"task_id\": 3,\n"
        "  \"worker_count\": 4,\n"
        "  \"material_type\": null,\n"
        "  \"quantity\": null,\n"
        "  \"message\": null,\n"
        "  \"actions\": null\n"
        "}\n\n"
        f"available_actions={available_list}\n"
        f"day={obs.day}, max_days={obs.max_days}, weather={obs.weather}, "
        f"workers_available={obs.workers_available}, budget_used={obs.budget_used:.3f}\n"
        f"equipment_health={obs.equipment_health}\n"
        f"cement_quality={obs.cement_quality}\n"
        f"active_issues={obs.active_issues}\n"
        f"valid_task_ids={get_valid_task_ids(obs)}\n"
        "tasks:\n- " + "\n- ".join(task_rows)
    )


def _format_observation_brief(obs: Any) -> str:
    blocked = sum(1 for t in obs.tasks if t.blocked)
    completed = sum(1 for t in obs.tasks if t.progress >= 1.0)
    total = len(obs.tasks)
    return (
        f"day={obs.day}, weather={obs.weather}, workers={obs.workers_available}, "
        f"budget_used={obs.budget_used:.3f}, completed={completed}/{total}, "
        f"blocked={blocked}"
    )


def _pick_worker_count(obs: Any, task_id: int) -> int:
    task_map = {t.task_id: t for t in obs.tasks}
    task = task_map.get(task_id)
    if task is None:
        return max(1, int(obs.workers_available))
    return min(
        max(1, int(obs.workers_available)),
        max(1, int(task.required_workers)),
    )


def _sanitize_action(action: ConstructionAction, obs: Any, valid_ids: list[int]) -> ConstructionAction:
    if not valid_ids:
        return ConstructionAction(action_type="do_nothing")

    if action.action_type == "allocate_workers":
        task_id = action.task_id if action.task_id in valid_ids else valid_ids[0]
        worker_count = action.worker_count or _pick_worker_count(obs, task_id)
        return ConstructionAction(
            action_type="allocate_workers",
            task_id=task_id,
            worker_count=worker_count,
        )

    if action.action_type == "allocate_workers_batch":
        allocations = []
        if action.allocations:
            for alloc in action.allocations:
                if alloc.task_id in valid_ids and alloc.worker_count and alloc.worker_count > 0:
                    allocations.append(alloc)
        if not allocations:
            task_id = valid_ids[0]
            return ConstructionAction(
                action_type="allocate_workers",
                task_id=task_id,
                worker_count=_pick_worker_count(obs, task_id),
            )
        return ConstructionAction(action_type="allocate_workers_batch", allocations=allocations)

    if action.action_type == "multi_action" and action.actions:
        cleaned = []
        for sub in action.actions:
            cleaned_sub = _sanitize_action(sub, obs, valid_ids)
            if cleaned_sub.action_type != "do_nothing":
                cleaned.append(cleaned_sub)
        if cleaned:
            return ConstructionAction(action_type="multi_action", actions=cleaned)
        task_id = valid_ids[0]
        return ConstructionAction(
            action_type="allocate_workers",
            task_id=task_id,
            worker_count=_pick_worker_count(obs, task_id),
        )

    return action


def _parse_action(raw: str, obs: Any) -> ConstructionAction:
    raw = (raw or "").strip()
    try:
        payload: Dict[str, Any] = json.loads(raw)
        if "action_type" not in payload:
            return _fallback_action(obs)
        return ConstructionAction(**payload)
    except Exception:
        return _fallback_action(obs)


def _choose_action(client: OpenAI, obs: Any, history: List[str]) -> ConstructionAction:
    user_prompt = _observation_to_prompt(obs)
    if history:
        user_prompt = (
            "Recent observations (most recent last):\n- "
            + "\n- ".join(history[-10:])
            + "\n\n"
            + user_prompt
        )
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a construction project decision agent acting as a junior project manager. "
                        "Your job is to choose the single best action for the current day to maximize: "
                        "task completion, time efficiency, cost efficiency, resource efficiency, and risk "
                        "reduction. Every decision must improve at least one without severely harming others. "
                        "Follow this mandatory process: classify the situation (scheduling, workforce, "
                        "material, risk, quality, strategy, meta); identify the biggest bottleneck; apply "
                        "priority order (unblock critical path > prevent near-future blocking > utilize idle "
                        "workers > reduce delays > optimize cost > strategic improvements); then choose the "
                        "best action from available_actions. Hard rules: never choose actions outside "
                        "available_actions, never assign workers to blocked tasks, never ignore dependencies, "
                        "never choose do_nothing if any useful action exists. Critical-path awareness: use "
                        "days_behind_schedule, priority, and blocked status as signals. Material planning: "
                        "order early to avoid shortages. Multi-step thinking: prefer actions that enable "
                        "progress in the next 2-3 steps. Output ONLY valid JSON (no markdown). If no clear "
                        "best action exists, choose request_pm_guidance and include a short proposed plan in "
                        "message."
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


# ─────────────────────────────────────────────────────
# SCORING
# ─────────────────────────────────────────────────────

def _compute_score(final_obs: Any, state: Optional[ConstructionState]) -> dict:
    tasks = list(final_obs.tasks)
    total = len(tasks)
    if total == 0:
        return {"score": 0.0, "breakdown": {}}

    completed = sum(1 for t in tasks if t.progress >= 1.0)
    completion_ratio = completed / total

    planned_end = max(t.planned_end_day for t in tasks)
    ideal_days = max(1, planned_end)
    actual_days = max(1, final_obs.day)
    time_efficiency = min(1.0, ideal_days / actual_days)

    if state is None:
        return {
            "score": round(completion_ratio, 4),
            "breakdown": {
                "completion_ratio": round(completion_ratio, 4),
                "time_efficiency": round(time_efficiency, 4),
            },
        }

    budget_overrun = max(0.0, state.total_cost - state.total_budget)
    cost_efficiency = max(
        0.0,
        1.0 - (budget_overrun / max(1, state.total_budget)),
    )

    total_workers = max(1, final_obs.total_workers)
    step_count = max(1, state.step_count)
    idle_ratio = min(1.0, state.cumulative_idle_workers / (step_count * total_workers))
    overtime_ratio = min(1.0, state.cumulative_overtime_hours / (step_count * 2.0))
    action_avg = state.cumulative_action_count / step_count
    action_complexity = min(1.0, max(0.0, (action_avg - 1.0) / 2.0))
    waste_ratio = min(1.0, state.cumulative_material_waste / max(1, state.total_budget))
    quality_penalty = (
        0.35 * overtime_ratio
        + 0.35 * idle_ratio
        + 0.20 * action_complexity
        + 0.10 * waste_ratio
    )
    quality_score = max(0.0, 1.0 - quality_penalty)

    score = (
        0.40 * completion_ratio
        + 0.30 * time_efficiency
        + 0.20 * cost_efficiency
        + 0.10 * quality_score
    )

    return {
        "score": round(max(0.0, min(1.0, score)), 4),
        "breakdown": {
            "completion_ratio": round(completion_ratio, 4),
            "time_efficiency": round(time_efficiency, 4),
            "cost_efficiency": round(cost_efficiency, 4),
            "quality_score": round(quality_score, 4),
            "idle_ratio": round(idle_ratio, 4),
            "overtime_ratio": round(overtime_ratio, 4),
            "action_complexity": round(action_complexity, 4),
            "material_waste_ratio": round(waste_ratio, 4),
        },
    }


# ─────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────

def main() -> None:
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN environment variable is required.")

    llm_client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)


    cumulative_reward = 0.0
    steps = 0
    action_counts: Dict[str, int] = {
        "allocate_workers": 0, "allocate_workers_batch": 0, "multi_action": 0,
        "order_material": 0, "reschedule_task": 0, "approve_overtime": 0,
        "request_pm_guidance": 0, "do_nothing": 0, "other": 0,
    }
    sub_action_counts: Dict[str, int] = {k: 0 for k in action_counts if k != "multi_action"}
    zero_progress_steps = 0
    reward_component_totals: Dict[str, float] = {}
    steps_with_reward_components = 0

    os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
    output_file = open(OUTPUT_PATH, "w", encoding="utf-8")

    def _write(line: str) -> None:
        print(line)
        output_file.write(line + "\n")

    with ConstructionEnv(base_url=ENV_BASE_URL).sync() as env:
        result = env.reset(difficulty=DIFFICULTY)
        observation_history: List[str] = []

        while (not result.done) and steps < MAX_STEPS:
            obs = result.observation
            progress_before = sum(float(t.progress) for t in obs.tasks)
            valid_ids = get_valid_task_ids(obs)

            observation_history.append(_format_observation_brief(obs))
            if len(observation_history) > 10:
                observation_history = observation_history[-10:]
            action = _choose_action(llm_client, obs, observation_history)
            action = _sanitize_action(action, obs, valid_ids)
            action_type = action.action_type if action.action_type in action_counts else "other"
            action_counts[action_type] += 1
            if action_type == "multi_action" and action.actions:
                for sub in action.actions:
                    sub_type = sub.action_type if sub.action_type in action_counts else "other"
                    sub_action_counts[sub_type] += 1
                    action_counts[sub_type] += 1

            result = env.step(action)
            reward = result.reward or 0.0
            cumulative_reward += reward
            reward_components = result.observation.reward_components or {}

            if DEBUG_STEPS:
                progress_after = sum(float(t.progress) for t in result.observation.tasks)
                alloc_count = len(action.allocations or []) if hasattr(action, "allocations") else 0
                _write(
                    f"Day {result.observation.day:3d} | {action.action_type:22s} | "
                    f"allocs={alloc_count} | "
                    f"workers={result.observation.workers_available}/{result.observation.total_workers} | "
                    f"delta={progress_after - progress_before:.3f} | "
                    f"reward={reward:+.3f}"
                )

            if reward_components:
                steps_with_reward_components += 1
            for name, value in reward_components.items():
                if isinstance(value, (int, float)):
                    reward_component_totals[name] = (
                        reward_component_totals.get(name, 0.0) + float(value)
                    )

            progress_after = sum(float(t.progress) for t in result.observation.tasks)
            if progress_after <= progress_before:
                zero_progress_steps += 1

            steps += 1

        final_obs = result.observation
        total_tasks = len(final_obs.tasks)
        completed_tasks = sum(
            1 for t in final_obs.tasks
            if t.progress >= 1.0 or t.status == "completed"
        )

        try:
            state = env.state()
        except Exception:
            state = None

        score_data = _compute_score(final_obs, state)

    summary = {
        "difficulty": DIFFICULTY,
        "steps": steps,
        "done": bool(result.done),
        "cumulative_reward": round(cumulative_reward, 4),
        "completed_tasks": completed_tasks,
        "total_tasks": total_tasks,
        "score": score_data.get("score", 0.0),
        "score_breakdown": score_data.get("breakdown", {}),
        "score_range_check": 0.0 <= score_data.get("score", 0.0) <= 1.0,
        "use_policy": False,
        "strategy_version": None,
        "action_counts": action_counts,
        "sub_action_counts": sub_action_counts,
        "zero_progress_steps": zero_progress_steps,
        "steps_with_reward_components": steps_with_reward_components,
        "reward_component_totals": {
            k: round(v, 4) for k, v in sorted(reward_component_totals.items())
        },
        "reward_component_avg_per_step": {
            k: round(v / max(1, steps), 4)
            for k, v in sorted(reward_component_totals.items())
        },
        "iron_triangle": {
            "time_performance": {
                "zero_progress_days": zero_progress_steps,
                "completion_score": round(completed_tasks / max(1, total_tasks), 4),
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
        },
    }

    _write(json.dumps(summary, indent=2))
    output_file.close()


if __name__ == "__main__":
    main()
