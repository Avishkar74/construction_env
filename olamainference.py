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
from typing import Any, Dict, List, Optional

import requests

from client import ConstructionEnv

from models import ConstructionAction, ConstructionState
try:
    from server.modules.action_catalog import ActionCatalog
except ModuleNotFoundError:
    from construction_env.server.modules.action_catalog import ActionCatalog

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
DIFFICULTY = os.getenv("DIFFICULTY", "medium")
MAX_STEPS = int(os.getenv("MAX_STEPS", "60"))
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "220"))
DEBUG_STEPS = os.getenv("DEBUG_STEPS", "0").lower() in ("0", "true", "yes")
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "outputs/olama_run.txt")
LOG_PATH = os.getenv("LOG_PATH", "outputs/olama_steps.txt")
CATALOG_PATH = os.path.join(os.path.dirname(__file__), "construction_actions_full.json")

CORE_ACTION_META = {
    "allocate_workers": ("workforce", "execution"),
    "allocate_workers_batch": ("workforce", "execution"),
    "order_material": ("material", "operations"),
    "approve_overtime": ("workforce", "operations"),
    "reschedule_task": ("scheduling", "operations"),
    "do_nothing": ("meta", "operations"),
    "request_pm_guidance": ("meta", "operations"),
    "multi_action": ("multi_action", "mixed"),
}


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
        "You are a construction project decision agent acting as a junior project manager.\n"
        "Your job is to choose the single best action for the current day to maximize overall project success.\n"
        "A multi_action counts as a single action that contains 2-5 sub-actions.\n\n"
        "OBJECTIVE FUNCTION (mandatory):\n"
        "1) Task completion (finish all tasks)\n"
        "2) Time efficiency (avoid delays)\n"
        "3) Cost efficiency (minimize cost and waste)\n"
        "4) Resource efficiency (avoid idle workers)\n"
        "5) Risk reduction (avoid future blockers)\n"
        "Every decision must improve at least ONE of these without severely harming others.\n\n"
        "DECISION FRAMEWORK (follow exactly):\n"
        "Step 1: Understand state: active tasks, blocked tasks, idle workers, material shortages, delays, and risks.\n"
        "Step 2: Identify the SINGLE biggest bottleneck (blocked critical task, idle workers, material shortage, "
        "schedule delay, cost inefficiency, or no actionable task).\n"
        "Step 3: Priority order (strict): unblock critical path > prevent near-future blocking > utilize idle workers > "
        "reduce delays > optimize cost > strategic improvements.\n"
        "Step 4: Candidate evaluation (critical): pick TOP 3 actions from available_actions (or all if fewer than 3). "
        "For each candidate, judge: progress gain, delay reduction, idle worker utilization, cost impact, and next-2-3-step benefits.\n"
        "Step 5: Choose the best action with the highest overall benefit and lowest negative side effects.\n\n"
        "HARD RULES:\n"
        "- Never choose actions outside available_actions.\n"
        "- Never assign workers to blocked tasks or ignore dependencies.\n"
        "- Choose do_nothing only when NO feasible or useful action exists today.\n"
        "- Never over-allocate workers beyond reasonable need for a task.\n"
        "- Prefer actions that create progress in the next 2-3 steps.\n\n"
        "ADVANCED RULES:\n"
        "- Cost awareness: avoid expensive actions unless they unblock critical path or prevent major delays.\n"
        "- Multi-action: use multi_action only when 2-5 complementary actions together beat any single action.\n"
        "  Every sub-action MUST be from available_actions and feasible today.\n\n"
        "VALIDATION RULES:\n"
        "- If choosing allocate_workers, task_id MUST be in valid_task_ids.\n"
        "- If choosing allocate_workers_batch, allocations MUST be non-empty and each task_id in valid_task_ids.\n\n"
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
        "Fallback: if no clear best action exists, choose request_pm_guidance and include a short proposed plan in message.\n\n"
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


def _get_action_meta(action_type: str, catalog: Optional[ActionCatalog]) -> tuple[str, str]:
    if action_type in CORE_ACTION_META:
        return CORE_ACTION_META[action_type]
    if catalog:
        entry = catalog.get(action_type)
        if entry:
            return entry.category, entry.phase
    return "unknown", "unknown"


def _estimate_action_cost(action_type: str, catalog: Optional[ActionCatalog]) -> Optional[float]:
    if not catalog:
        return None
    entry = catalog.get(action_type)
    if not entry:
        return None
    variables = catalog.build_variables(entry)
    return catalog.compute_cost(entry, variables)


def _choose_action(obs: Any, history: List[str]) -> ConstructionAction:
    prompt = _observation_to_prompt(obs)
    if history:
        prompt = (
            "Recent observations (most recent last):\n- "
            + "\n- ".join(history[-10:])
            + "\n\n"
            + prompt
        )
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
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
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {
                    "temperature": TEMPERATURE,
                    "num_predict": MAX_TOKENS,
                },
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        text = payload.get("message", {}).get("content", "")
    except Exception:
        return _fallback_action(obs)
    return _parse_action(text, obs)


def _compute_score(final_obs, state: Optional[ConstructionState]) -> dict:
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



def main() -> None:
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
    sub_action_counts = {k: 0 for k in action_counts if k != "multi_action"}
    zero_progress_steps = 0
    reward_component_totals: dict[str, float] = {}
    steps_with_reward_components = 0

    os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)
    output_file = open(OUTPUT_PATH, "w", encoding="utf-8")
    log_file = open(LOG_PATH, "w", encoding="utf-8")

    def _write(line: str) -> None:
        print(line)
        log_file.write(line + "\n")

    with ConstructionEnv(base_url=ENV_BASE_URL).sync() as env:
        result = env.reset(difficulty=DIFFICULTY)
        observation_history: List[str] = []
        action_catalog = ActionCatalog.load(CATALOG_PATH)
        last_available_actions: Optional[str] = None
        prev_budget_used_ratio: Optional[float] = None

        initial_obs = result.observation
        task_titles = [f"{t.task_id}:{t.title}" for t in initial_obs.tasks]
        _write("Project metadata:")
        _write(f"  - difficulty={DIFFICULTY}")
        _write(f"  - max_days={initial_obs.max_days}")
        _write(f"  - total_workers={initial_obs.total_workers}")
        _write(f"  - budget_total={initial_obs.budget_total}")
        _write(f"  - starting_materials={initial_obs.materials_available}")
        _write(f"  - equipment_health={initial_obs.equipment_health}")
        _write(f"  - tasks={task_titles}")

        while (not result.done) and steps < MAX_STEPS:
            obs = result.observation
            progress_before = sum(float(t.progress) for t in obs.tasks)
            valid_ids = get_valid_task_ids(obs)
            task_map = {t.task_id: t for t in obs.tasks}
            available_actions = list(getattr(obs, "available_actions", []) or [])
            available_actions_text = ", ".join(available_actions)
            observation_history.append(_format_observation_brief(obs))
            if len(observation_history) > 10:
                observation_history = observation_history[-10:]
            if DEBUG_STEPS and available_actions_text != last_available_actions:
                _write(f"  - available_actions={available_actions_text}")
                last_available_actions = available_actions_text
            llm_action = _choose_action(obs, observation_history)
            action = _sanitize_action(llm_action, obs, valid_ids)
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
                budget_used_ratio = result.observation.budget_used
                budget_delta = None
                if prev_budget_used_ratio is not None:
                    budget_delta = (budget_used_ratio - prev_budget_used_ratio) * result.observation.budget_total
                prev_budget_used_ratio = budget_used_ratio
                est_action_cost = _estimate_action_cost(action.action_type, action_catalog)
                equipment_cost = None
                if action.action_type in ("book_equipment", "schedule_equipment", "mobilize_equipment"):
                    equipment_cost = est_action_cost
                llm_category, llm_phase = _get_action_meta(llm_action.action_type, action_catalog)
                chosen_category, chosen_phase = _get_action_meta(action.action_type, action_catalog)
                _write(
                    "  - llm_choice="
                    f"{llm_action.action_type}(task_id={llm_action.task_id})"
                    f" | category={llm_category} | phase={llm_phase}"
                )
                if llm_action.action_type != action.action_type or llm_action.task_id != action.task_id:
                    _write(
                        "  - applied_action="
                        f"{action.action_type}(task_id={action.task_id})"
                        f" | category={chosen_category} | phase={chosen_phase}"
                    )
                allocations_count = len(action.allocations or []) if hasattr(action, "allocations") else 0
                progress_after = sum(float(t.progress) for t in result.observation.tasks)
                progress_delta = progress_after - progress_before
                task_title = None
                task_status = None
                task_progress = None
                if action.task_id is not None:
                    task_info = task_map.get(action.task_id)
                    task_title = task_info.title if task_info else None
                    task_status = task_info.status if task_info else None
                    task_progress = task_info.progress if task_info else None
                task_label = f"{action.task_id}:{task_title}" if task_title else f"{action.task_id}"
                status_label = task_status if task_status else "unknown"
                progress_label = f"{task_progress:.2f}" if task_progress is not None else "n/a"
                worker_count = action.worker_count or 0
                workers_label = (
                    f"workers_assigned={worker_count}"
                    if action.action_type == "allocate_workers"
                    else f"allocations={allocations_count}"
                )
                line = (
                    f"Day {result.observation.day:2d} | {action.action_type:22s} | "
                    f"task={task_label} | {workers_label} | "
                    f"workers={result.observation.workers_available}/{result.observation.total_workers} | "
                    f"status={status_label} | progress={progress_label} | "
                    f"delta={progress_delta:.3f} | reward={reward:+.3f}"
                )
                _write(line)
                if budget_delta is not None:
                    _write(
                        f"  - budget_used={budget_used_ratio:.3f} | budget_delta={budget_delta:.2f}"
                    )
                else:
                    _write(f"  - budget_used={budget_used_ratio:.3f}")
                if est_action_cost is not None:
                    _write(f"  - est_action_cost={est_action_cost:.2f}")
                if equipment_cost is not None:
                    _write(f"  - equipment_rental_cost={equipment_cost:.2f}")
                if valid_ids:
                    valid_titles = [
                        f"{tid}:{task_map.get(tid).title}" if task_map.get(tid) else str(tid)
                        for tid in valid_ids
                    ]
                    _write(f"  - valid_tasks={valid_titles}")
                if action.action_type == "multi_action" and action.actions:
                    for sub in action.actions:
                        sub_allocs = len(sub.allocations or []) if hasattr(sub, "allocations") else 0
                        sub_title = None
                        sub_status = None
                        sub_progress = None
                        if sub.task_id is not None:
                            sub_info = task_map.get(sub.task_id)
                            sub_title = sub_info.title if sub_info else None
                            sub_status = sub_info.status if sub_info else None
                            sub_progress = sub_info.progress if sub_info else None
                        sub_label = f"{sub.task_id}:{sub_title}" if sub_title else f"{sub.task_id}"
                        sub_status_label = sub_status if sub_status else "unknown"
                        sub_progress_label = (
                            f"{sub_progress:.2f}" if sub_progress is not None else "n/a"
                        )
                        sub_category, sub_phase = _get_action_meta(sub.action_type, action_catalog)
                        _write(
                            f"  - {sub.action_type} | task={sub_label} | "
                            f"status={sub_status_label} | progress={sub_progress_label} | "
                            f"category={sub_category} | phase={sub_phase} | "
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
        "ollama_model": OLLAMA_MODEL,
        "ollama_url": OLLAMA_URL,
        "strategy_version": None,
        "action_counts": action_counts,
        "sub_action_counts": sub_action_counts,
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
    }

    output_file.write(json.dumps(summary, indent=2) + "\n")
    output_file.close()
    log_file.close()


if __name__ == "__main__":
    main()
