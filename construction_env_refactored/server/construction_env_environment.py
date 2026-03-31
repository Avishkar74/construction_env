# server/construction_env_environment.py
"""
ConstructionEnvironment — Full implementation with all critical fixes:

  FIX 1: bad_action is now correctly set to True for invalid allocations
  FIX 2: budget_ratio computed AFTER costs applied (not stale)
  FIX 3: _auto_reschedule preserves task duration (fixes phantom delay)
  FIX 4: Equipment health passed to task progress update
  FIX 5: All new event module events wired in (rework, delivery delay, price)
  FIX 6: Cement quality exposed in observation
  FIX 7: Worker allocation cap respects crowding logic
"""
from __future__ import annotations

import random
import uuid
import sys
import os
import logging
import math
from typing import Dict, List, Literal, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openenv.core.env_server import Environment

from models import (
    ConstructionAction,
    ConstructionObservation,
    ConstructionState,
    MaterialOrder,
    TaskObservation,
)
from server.modules.task_module import Task, TaskModule
from server.modules.event_module import EventModule
from server.modules.material_module import MaterialModule
from server.modules.workforce_module import WorkforceModule
from server.modules.chat_module import ChatModule
from server.configs.difficulty import get_task_config, DIFFICULTY_SETTINGS


OBSERVATION_NOISE_STD = 0.04
logger = logging.getLogger(__name__)


class ConstructionEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        self._state = ConstructionState()
        self._task_module = TaskModule()
        self._event_module = EventModule()
        self._material_module = MaterialModule()
        self._workforce_module = WorkforceModule(total_workers=20)
        self._chat_module = ChatModule()
        self._workers_available = 20

    # ─────────────────────────────────────────────────────
    # RESET
    # ─────────────────────────────────────────────────────

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        difficulty: Literal["easy", "medium", "hard"] = "medium",
        **kwargs,
    ) -> ConstructionObservation:
        if seed is not None:
            random.seed(seed)

        settings = DIFFICULTY_SETTINGS[difficulty]
        task_configs = get_task_config(difficulty)

        tasks = [Task(**cfg) for cfg in task_configs]
        self._task_module.load(tasks)

        self._event_module = EventModule(difficulty=difficulty)
        self._material_module.initialize(
            dict(settings["starting_materials"]), start_day=1
        )
        total_workers = settings["total_workers"]
        self._workforce_module = WorkforceModule(total_workers=total_workers)
        self._workers_available = total_workers

        self._state = ConstructionState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            current_day=1,
            difficulty=difficulty,
            max_days=settings["max_days"],
            true_task_progress={t.task_id: 0.0 for t in tasks},
            worker_efficiency=1.0,
            overtime_fatigue=0.0,
            pending_orders=[],
            equipment_health={"crane": 1.0, "excavator": 1.0},
            total_budget=settings["total_budget"],
            total_cost=0.0,
            total_delay_days=0,
            current_weather="clear",
        )

        return self._build_observation(done=False, reward=0.0)

    # ─────────────────────────────────────────────────────
    # STEP
    # ─────────────────────────────────────────────────────

    def step(
        self,
        action: ConstructionAction,
        timeout_s: Optional[float] = None,
        **kwargs,
    ) -> ConstructionObservation:
        self._state.step_count += 1
        self._state.current_day += 1
        day = self._state.current_day

        # ── 0. Free all workers (fresh day) ──────────────
        self._task_module.free_all_workers()
        self._workers_available = self._workforce_module.total_workers

        # ── 1. Roll events ────────────────────────────────
        weather, weather_modifier = self._event_module.roll_weather()
        self._state.current_weather = weather

        workers_lost, worker_issues = self._event_module.roll_worker_absence(
            self._workforce_module.total_workers
        )
        self._workers_available = max(0, self._workers_available - workers_lost)

        equip_health, equip_issues = self._event_module.roll_equipment_failure(
            dict(self._state.equipment_health)
        )
        self._state.equipment_health = equip_health
        self._state.active_issues = worker_issues + equip_issues

        # ── 2. Apply agent action ─────────────────────────
        step_cost = self._workforce_module.daily_labor_cost(
            min(self._workers_available, self._workforce_module.total_workers)
        )

        self._auto_reschedule_ready_tasks(day)

        bad_action = False
        actions_to_apply = (
            list(action.actions)
            if action.action_type == "multi_action" and action.actions
            else [action]
        )

        action_count = len(actions_to_apply)
        self._state.last_action_count = action_count
        self._state.cumulative_action_count += action_count
        if action.action_type == "multi_action":
            self._state.cumulative_multi_action_count += 1

        # Categorise sub-actions
        order_actions = [
            a for a in actions_to_apply
            if a.action_type == "order_material" and a.material_type
        ]
        reschedule_actions = [
            a for a in actions_to_apply
            if a.action_type == "reschedule_task" and a.task_id is not None
        ]
        overtime_actions = [
            a for a in actions_to_apply
            if a.action_type == "approve_overtime" and a.task_id is not None
        ]
        allocation_actions = [
            a for a in actions_to_apply
            if a.action_type in ("allocate_workers", "allocate_workers_batch")
        ]

        # Material orders
        for a in order_actions:
            order = self._material_module.place_order(
                a.material_type, a.quantity or 10.0, day, self._state.difficulty
            )
            self._state.pending_orders.append(order)
            step_cost += order.cost

        # Reschedule
        for a in reschedule_actions:
            task = self._task_module.tasks.get(a.task_id)
            if task and a.new_start_day is not None:
                original_duration = task.planned_end - task.planned_start
                task.planned_start = a.new_start_day
                task.planned_end = a.new_start_day + original_duration

        # Auto-inject allocation when only ordering
        if not allocation_actions and order_actions:
            allocation_actions = [ConstructionAction(action_type="allocate_workers")]

        # Pre-compute budget ratio for cap logic (use running total)
        budget_ratio_pre = self._state.total_cost / max(1.0, self._state.total_budget)

        # Worker allocations
        for a in allocation_actions:
            allocations: list = []
            if a.action_type == "allocate_workers_batch" and a.allocations:
                allocations = [
                    {"task_id": alloc.task_id, "worker_count": alloc.worker_count}
                    for alloc in a.allocations
                ]
            elif a.action_type == "allocate_workers" and a.task_id is not None:
                allocations = [
                    {"task_id": a.task_id, "worker_count": a.worker_count or 0}
                ]
            else:
                # Fallback: server-side dynamic allocation
                current_obs = self._build_observation(done=False, reward=0.0)
                allocations = self._compute_dynamic_allocations(current_obs)
                logger.debug("Day %s: server-side dynamic allocation used.", day)

            for alloc in allocations:
                if self._workers_available <= 0:
                    break
                task_id = int(alloc.get("task_id", -1))
                worker_count = max(0, int(alloc.get("worker_count", 0)))
                task = self._task_module.tasks.get(task_id)

                # ── FIX 1: properly detect bad actions ──
                if task is None:
                    bad_action = True
                    continue
                if task.blocked or task.true_progress >= 1.0:
                    bad_action = True
                    logger.debug(
                        "Bad action day %s: task %s blocked=%s progress=%.2f",
                        day, task_id, task.blocked, task.true_progress,
                    )
                    continue
                if worker_count <= 0:
                    bad_action = True
                    continue

                base_cap = max(1, task.required_workers)
                if budget_ratio_pre < 0.8:
                    cap_mult = 1.5
                elif budget_ratio_pre < 0.9:
                    cap_mult = 1.2
                else:
                    cap_mult = 1.0
                if task.true_progress >= 0.7:
                    cap_mult = max(cap_mult, 1.2)

                cap = math.ceil(base_cap * cap_mult)
                if worker_count < base_cap:
                    continue  # not enough to make progress — skip without penalty

                worker_count = min(worker_count, cap, self._workers_available)
                allocated = self._task_module.assign_workers(
                    task_id, worker_count, self._workers_available
                )
                self._workers_available -= allocated

        # Overtime
        total_overtime_hours = 0.0
        for a in overtime_actions:
            hours = max(0, a.overtime_hours or 2)
            total_overtime_hours += hours
            task = self._task_module.tasks.get(a.task_id) if a.task_id is not None else None
            workers_on_task = task.assigned_workers if task is not None else None
            self._workforce_module.apply_overtime(hours)
            step_cost += self._workforce_module.overtime_cost(hours, workers_on_task)

        self._state.last_overtime_hours = total_overtime_hours
        self._state.cumulative_overtime_hours += total_overtime_hours

        # ── 3. Stochastic market/delivery events ─────────
        material_costs, price_issues = self._event_module.roll_price_escalation(
            dict(self._material_module.material_costs)
        )
        if price_issues:
            self._state.active_issues.extend(price_issues)
        self._material_module.update_material_costs(material_costs)

        delayed_orders, delay_issues = self._event_module.roll_material_delivery_delay(
            list(self._state.pending_orders)
        )
        if delay_issues:
            self._state.active_issues.extend(delay_issues)
        self._state.pending_orders = delayed_orders

        # ── 4. Process deliveries ─────────────────────────
        self._state.pending_orders = self._material_module.process_deliveries(
            list(self._state.pending_orders), day
        )

        # Material spoilage
        spoilage_issues = self._material_module.age_inventory(day)
        if spoilage_issues:
            self._state.active_issues.extend(spoilage_issues)
        spoilage_loss = 0.0
        for issue in spoilage_issues:
            if ":" in issue:
                try:
                    spoilage_loss += float(issue.split(":", 1)[1])
                except ValueError:
                    pass
        self._state.last_material_waste = spoilage_loss
        self._state.cumulative_material_waste += spoilage_loss

        # ── 5. Task progress update ───────────────────────
        total_progress_before = sum(
            t.true_progress for t in self._task_module.tasks.values()
        )
        cement_quality = self._material_module.get_cement_quality(day)

        self._task_module.update_all(
            current_day=day,
            weather_modifier=weather_modifier,
            weather=weather,
            efficiency=self._workforce_module.efficiency,
            materials_available=self._material_module.inventory,
            pending_orders=list(self._state.pending_orders),
            equipment_health=self._state.equipment_health,   # ── FIX 4
            cement_quality=cement_quality,
        )

        # Quality rework events
        tasks_after, rework_issues = self._event_module.roll_quality_rework(
            self._task_module.tasks
        )
        self._task_module.tasks = tasks_after
        if rework_issues:
            self._state.active_issues.extend(rework_issues)

        total_progress_after = sum(
            t.true_progress for t in self._task_module.tasks.values()
        )
        progress_gain = total_progress_after - total_progress_before

        # ── 6. Sync true progress ─────────────────────────
        for tid, task in self._task_module.tasks.items():
            self._state.true_task_progress[tid] = task.true_progress

        # ── 7. Workforce end-of-day ───────────────────────
        workers_used = self._workforce_module.total_workers - self._workers_available
        self._workforce_module.end_of_day(workers_used)
        self._state.worker_efficiency = self._workforce_module.efficiency
        self._state.overtime_fatigue = self._workforce_module.fatigue
        self._state.cumulative_idle_workers += max(0, self._workers_available)

        # ── 8. Cost — FIX 2: accumulate BEFORE computing ratio ──
        self._state.total_cost = min(
            self._state.total_cost + step_cost,
            self._state.total_budget * 2.0,
        )
        budget_ratio = self._state.total_cost / max(1.0, self._state.total_budget)

        # ── 9. Delay tracking ─────────────────────────────
        self._state.total_delay_days = self._task_module.total_delay_days(day)

        # ── 10. Reward ────────────────────────────────────
        reward, reward_components = self._compute_reward(
            progress_gain=progress_gain,
            weather=weather,
            bad_action=bad_action,
            budget_ratio=budget_ratio,  # now accurate
            day=day,
            action_count=action_count,
            overtime_hours=total_overtime_hours,
            zero_progress=(progress_gain <= 0.0),
        )
        if bad_action:
            self._state.cumulative_bad_action_count += 1
        if progress_gain <= 0.0:
            self._state.cumulative_zero_progress_days += 1

        # ── 11. Done ──────────────────────────────────────
        done = self._task_module.all_complete() or day >= self._state.max_days

        return self._build_observation(
            done=done,
            reward=round(reward, 4),
            reward_components=reward_components,
        )

    # ─────────────────────────────────────────────────────
    # STATE PROPERTY
    # ─────────────────────────────────────────────────────

    @property
    def state(self) -> ConstructionState:
        return self._state

    # ─────────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────────────────

    def _auto_reschedule_ready_tasks(self, current_day: int) -> None:
        """
        FIX 3: preserves task duration when pulling forward or pushing back.
        """
        for task in self._task_module.tasks.values():
            if task.true_progress >= 1.0:
                continue
            if task.actual_start is not None:
                continue  # already started — don't move
            if not task.is_unblocked(self._task_module.tasks):
                continue

            original_duration = task.planned_end - task.planned_start

            if current_day < task.planned_start:
                # Pull forward (dependency met early)
                task.planned_start = current_day
                task.planned_end = current_day + original_duration
            elif current_day > task.planned_start:
                # Push back (couldn't start on time)
                task.planned_start = current_day
                task.planned_end = current_day + original_duration

    def _compute_dynamic_allocations(
        self, obs: ConstructionObservation
    ) -> list:
        """Server-side fallback allocation when agent sends bare allocate_workers."""
        workers = obs.workers_available
        tasks = [
            t for t in obs.tasks
            if (not t.blocked) and t.progress < 1.0
        ]
        if not tasks or workers <= 0:
            return []

        def score(t):
            s = 0.0
            if t.priority == "critical":
                s += 100.0
            elif t.priority == "high":
                s += 70.0
            elif t.priority == "medium":
                s += 40.0
            s += (1.0 - t.progress) * max(1, t.required_workers) * 10.0
            s += max(0, t.days_behind_schedule) * 50.0
            if t.progress > 0.6:
                s += 80.0
            return s

        tasks.sort(key=score, reverse=True)
        allocations = []
        for t in tasks:
            if workers <= 0:
                break
            min_needed = max(1, t.required_workers)
            if workers < min_needed:
                continue
            assign = min(workers, min_needed)
            if t.progress > 0.7:
                assign = workers  # finish it off
            allocations.append({"task_id": t.task_id, "worker_count": assign})
            workers -= assign
        return allocations

    # ─────────────────────────────────────────────────────
    # REWARD
    # ─────────────────────────────────────────────────────

    def _compute_reward(
        self,
        progress_gain: float,
        weather: str,
        bad_action: bool,
        budget_ratio: float,
        day: int,
        action_count: int,
        overtime_hours: float,
        zero_progress: bool,
    ):
        c: dict = {}

        # Primary: progress
        c["progress"] = progress_gain * 2.5

        # Worker efficiency
        workers_used = self._workforce_module.total_workers - self._workers_available
        efficiency_ratio = (
            workers_used / self._workforce_module.total_workers
            if self._workforce_module.total_workers > 0 else 0.0
        )
        c["efficiency"] = efficiency_ratio * 1.0

        # Idle penalty
        c["idle_penalty"] = -self._workers_available * 0.12

        # Delay penalty
        delay_days = self._task_module.total_delay_days(day)
        c["delay_penalty"] = -delay_days * 0.4

        # Bad action
        c["bad_action"] = -1.5 if bad_action else 0.0

        # Action complexity penalty
        c["action_penalty"] = -0.2 * max(0, action_count - 1)

        # Overtime penalty
        c["overtime_penalty"] = -0.15 * max(0.0, overtime_hours)

        # Zero-progress day
        c["zero_progress_penalty"] = -0.5 if zero_progress else 0.0

        # Budget pressure
        c["budget_pressure"] = (
            -((budget_ratio - 0.9) * 3.0) if budget_ratio > 0.9 else 0.0
        )

        # Storm penalty
        c["weather_penalty"] = -0.3 if weather == "storm" else 0.0

        raw = sum(c.values())
        clipped = max(-5.0, min(5.0, raw))
        c["raw_reward"] = raw
        c["clipped_reward"] = clipped
        return clipped, c

    # ─────────────────────────────────────────────────────
    # BUILD OBSERVATION
    # ─────────────────────────────────────────────────────

    def _build_observation(
        self,
        done: bool,
        reward: float,
        reward_components: dict | None = None,
    ) -> ConstructionObservation:
        day = self._state.current_day
        difficulty = self._state.difficulty
        total_workers = self._workforce_module.total_workers

        tasks_obs = []
        for task in self._task_module.tasks.values():
            noisy_progress = task.true_progress
            if 0.0 < noisy_progress < 1.0:
                noise = random.gauss(0, OBSERVATION_NOISE_STD)
                noisy_progress = max(0.0, min(0.99, noisy_progress + noise))

            est_workers = max(1, task.assigned_workers or task.required_workers)
            est_rate = 0.02 * (est_workers ** 0.85)
            remaining = max(0.0, 1.0 - task.true_progress)
            est_days = int(math.ceil(remaining / est_rate)) if est_rate > 0 else 0
            est_completion = day + est_days if remaining > 0 else day

            tasks_obs.append(
                TaskObservation(
                    task_id=task.task_id,
                    title=task.title,
                    description=task.description,
                    status=task.status,
                    progress=round(noisy_progress, 3),
                    planned_start_day=task.planned_start,
                    planned_end_day=task.planned_end,
                    priority=task.priority,
                    is_critical_path=task.is_critical_path,
                    dependencies=task.dependencies,
                    blocked=task.blocked,
                    required_workers=task.required_workers,
                    assigned_workers=task.assigned_workers,
                    required_materials=task.required_materials,
                    days_behind_schedule=task.days_behind(day),
                    estimated_completion_day=est_completion,
                    worker_hours_logged=round(task.worker_hours_logged, 2),
                    rework_count=task.rework_count,
                )
            )

        budget_ratio = self._state.total_cost / max(1.0, self._state.total_budget)
        cement_quality = self._material_module.get_cement_quality(day)

        chat = self._chat_module.generate(
            current_day=day,
            max_days=self._state.max_days,
            task_module=self._task_module,
            workers_available=self._workers_available,
            total_workers=total_workers,
            materials=self._material_module.inventory,
            weather=self._state.current_weather,
            budget_ratio=budget_ratio,
            difficulty=difficulty,
        )

        return ConstructionObservation(
            done=done,
            reward=reward,
            day=day,
            max_days=self._state.max_days,
            tasks=tasks_obs,
            workers_available=self._workers_available,
            total_workers=total_workers,
            overtime_fatigue_level=round(self._state.overtime_fatigue, 3),
            materials_available=self._material_module.get_inventory_snapshot(),
            pending_orders=[o.model_dump() for o in self._state.pending_orders],
            weather=self._state.current_weather,
            active_issues=list(self._state.active_issues),
            reward_components=reward_components,
            budget_total=self._state.total_budget,
            budget_used=round(budget_ratio, 4),
            chat_messages=chat,
            difficulty=difficulty,
            equipment_health=dict(self._state.equipment_health),
            critical_path_tasks=[
                t.task_id
                for t in self._task_module.tasks.values()
                if t.is_critical_path
            ],
            days_remaining=max(0, self._state.max_days - day),
            overall_progress=round(
                sum(t.true_progress for t in self._task_module.tasks.values())
                / max(1, len(self._task_module.tasks)),
                4,
            ),
            idle_workers_ratio=round(
                self._workers_available / max(1, total_workers), 4
            ),
            overtime_hours=round(self._state.last_overtime_hours, 2),
            material_waste=round(self._state.last_material_waste, 2),
            delay_penalty=round(
                min(
                    1.0,
                    self._state.total_delay_days
                    / max(1, self._state.max_days * 0.2),
                ),
                4,
            ),
            cement_quality=round(cement_quality, 3),
        )

    # ─────────────────────────────────────────────────────
    # GRADER
    # ─────────────────────────────────────────────────────

    def compute_score(self) -> Dict:
        tasks = list(self._task_module.tasks.values())
        total = len(tasks)
        if total == 0:
            return {"score": 0.0}

        completed = sum(1 for t in tasks if t.true_progress >= 1.0)
        completion_ratio = completed / total

        planned_end = max(t.planned_end for t in tasks)
        ideal_days = max(1, planned_end)
        actual_days = max(1, self._state.current_day)
        time_efficiency = min(1.0, ideal_days / actual_days)

        budget_overrun = max(
            0.0, self._state.total_cost - self._state.total_budget
        )
        cost_efficiency = max(
            0.0,
            1.0 - (budget_overrun / max(1, self._state.total_budget)),
        )

        total_workers = max(1, self._workforce_module.total_workers)
        step_count = max(1, self._state.step_count)
        idle_ratio = min(
            1.0,
            self._state.cumulative_idle_workers / (step_count * total_workers),
        )
        overtime_ratio = min(
            1.0,
            self._state.cumulative_overtime_hours / (step_count * 2.0),
        )
        action_avg = self._state.cumulative_action_count / step_count
        action_complexity = min(1.0, max(0.0, (action_avg - 1.0) / 2.0))
        waste_ratio = min(
            1.0,
            self._state.cumulative_material_waste
            / max(1, self._state.total_budget),
        )
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
