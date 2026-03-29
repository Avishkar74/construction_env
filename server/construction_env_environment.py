# server/environment.py
from __future__ import annotations

import random
import uuid
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import Dict, List, Literal, Optional
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


OBSERVATION_NOISE_STD = 0.04   # Gaussian noise added to observed progress


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

    # ──────────────────────────────────────────
    # RESET
    # ──────────────────────────────────────────

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

        # Build tasks
        tasks = [Task(**cfg) for cfg in task_configs]
        self._task_module.load(tasks)

        # Initialize modules
        self._event_module = EventModule(difficulty=difficulty)
        self._material_module.initialize(dict(settings["starting_materials"]))
        total_workers = settings["total_workers"]
        self._workforce_module = WorkforceModule(total_workers=total_workers)
        self._workers_available = total_workers

        # Initialize state
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

    # ──────────────────────────────────────────
    # STEP
    # ──────────────────────────────────────────

    def step(
        self,
        action: ConstructionAction,
        timeout_s: Optional[float] = None,
        **kwargs,
    ) -> ConstructionObservation:
        self._state.step_count += 1
        self._state.current_day += 1
        day = self._state.current_day

        # ── 0. Free all workers (fresh day, fresh allocation) ──
        self._task_module.free_all_workers()
        self._workers_available = self._workforce_module.total_workers

        # ── 1. Roll events BEFORE applying action (agent acts with knowledge of weather) ──
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
        all_issues = worker_issues + equip_issues
        # expose active issues in state for observability
        self._state.active_issues = all_issues

        # ── 2. Apply agent action ──
        step_cost = 0.0
        step_cost += self._workforce_module.daily_labor_cost(
            min(self._workers_available, self._workforce_module.total_workers)
        )

        bad_action = False
        if action.action_type == "allocate_workers" and action.task_id is not None:
            task = self._task_module.tasks.get(action.task_id)
            if task and task.blocked:
                bad_action = True   # penalize allocating to a blocked task
            allocated = self._task_module.assign_workers(
                action.task_id,
                action.worker_count or 0,
                self._workers_available,
            )
            self._workers_available -= allocated

        elif action.action_type == "order_material" and action.material_type:
            order = self._material_module.place_order(
                action.material_type,
                action.quantity or 10.0,
                day,
                self._state.difficulty,
            )
            self._state.pending_orders.append(order)
            step_cost += order.cost

        elif action.action_type == "approve_overtime" and action.task_id is not None:
            hours = action.overtime_hours or 2
            self._workforce_module.apply_overtime(hours)
            step_cost += self._workforce_module.overtime_cost(hours)
            # Re-assign all available workers with overtime boost to this task
            allocated = self._task_module.assign_workers(
                action.task_id,
                self._workers_available,
                self._workers_available,
            )
            self._workers_available -= allocated

        elif action.action_type == "reschedule_task" and action.task_id is not None:
            task = self._task_module.tasks.get(action.task_id)
            if task and action.new_start_day:
                task.planned_start = action.new_start_day

        # ── 3. Process material deliveries (removes delivered orders) ──
        self._state.pending_orders = self._material_module.process_deliveries(
            list(self._state.pending_orders), day
        )

        # ── 4. Update all task progress ──
        progress_gain = self._task_module.update_all(
            current_day=day,
            weather_modifier=weather_modifier,
            efficiency=self._workforce_module.efficiency,
            materials_available=self._material_module.inventory,
        )

        # ── 5. Sync true_task_progress into state ──
        for tid, task in self._task_module.tasks.items():
            self._state.true_task_progress[tid] = task.true_progress

        # ── 6. Update workforce end-of-day ──
        workers_used = self._workforce_module.total_workers - self._workers_available
        self._workforce_module.end_of_day(workers_used)
        self._state.worker_efficiency = self._workforce_module.efficiency
        self._state.overtime_fatigue = self._workforce_module.fatigue

        # ── 7. Accumulate cost ──
        self._state.total_cost += step_cost

        # ── 8. Update delay tracking ──
        self._state.total_delay_days = self._task_module.total_delay_days(day)

        # ── 9. Generate contextual chat ──
        budget_ratio = self._state.total_cost / max(1, self._state.total_budget)

        # ── 10. Compute reward ──
        reward, reward_components = self._compute_reward(
            progress_gain=progress_gain,
            weather=weather,
            bad_action=bad_action,
            budget_ratio=budget_ratio,
            day=day,
        )

        # ── 11. Check done ──
        done = self._task_module.all_complete() or day >= self._state.max_days

        return self._build_observation(done=done, reward=round(reward, 4), reward_components=reward_components)

    # ──────────────────────────────────────────
    # STATE PROPERTY
    # ──────────────────────────────────────────

    @property
    def state(self) -> ConstructionState:
        return self._state

    # ──────────────────────────────────────────
    # REWARD
    # ──────────────────────────────────────────

    def _compute_reward(
        self,
        progress_gain: float,
        weather: str,
        bad_action: bool,
        budget_ratio: float,
        day: int,
    ) -> tuple[float, dict]:
        components: dict = {}

        # Primary: progress made
        components['progress'] = progress_gain * 2.5

        # Efficiency: proportion of workers actually doing useful work
        workers_used = self._workforce_module.total_workers - self._workers_available
        efficiency_ratio = 0.0
        if self._workforce_module.total_workers > 0:
            efficiency_ratio = workers_used / self._workforce_module.total_workers
        components['efficiency'] = efficiency_ratio * 1.0

        # Idle worker penalty
        idle = self._workers_available
        components['idle_penalty'] = - idle * 0.12

        # Delay penalty (per task per day behind)
        delay_days = self._task_module.total_delay_days(day)
        components['delay_penalty'] = - delay_days * 0.4

        # Bad action (allocating to blocked task)
        components['bad_action'] = -1.5 if bad_action else 0.0

        # Budget pressure
        components['budget_pressure'] = -((budget_ratio - 0.9) * 3.0) if budget_ratio > 0.9 else 0.0

        # Storm day penalty
        components['weather_penalty'] = -0.3 if weather == 'storm' else 0.0

        raw_reward = sum(components.values())
        clipped = max(-5.0, min(5.0, raw_reward))
        components['raw_reward'] = raw_reward
        components['clipped_reward'] = clipped

        return clipped, components

    # ──────────────────────────────────────────
    # BUILD OBSERVATION (adds noise to hide true state)
    # ──────────────────────────────────────────

    def _build_observation(self, done: bool, reward: float, reward_components: dict | None = None) -> ConstructionObservation:
        day = self._state.current_day
        difficulty = self._state.difficulty
        total_workers = self._workforce_module.total_workers

        # Build task observations WITH NOISE on progress
        tasks_obs = []
        for task in self._task_module.tasks.values():
            # Add Gaussian noise to progress (hidden state feature)
            noisy_progress = task.true_progress
            if 0.0 < noisy_progress < 1.0:
                noise = random.gauss(0, OBSERVATION_NOISE_STD)
                noisy_progress = max(0.0, min(0.99, noisy_progress + noise))

            tasks_obs.append(TaskObservation(
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
            ))

        budget_ratio = self._state.total_cost / max(1, self._state.total_budget)

        # Generate contextual chat
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
            active_issues=getattr(self._state, 'active_issues', []),
            reward_components=reward_components,
            budget_total=self._state.total_budget,
            budget_used=round(budget_ratio, 4),
            chat_messages=chat,
            difficulty=difficulty,
        )

    # ──────────────────────────────────────────
    # GRADER (called from app.py endpoint)
    # ──────────────────────────────────────────

    def compute_score(self) -> Dict:
        """Deterministic score 0.0–1.0 based on current episode performance."""
        tasks = list(self._task_module.tasks.values())
        total = len(tasks)
        if total == 0:
            return {"score": 0.0}

        # Completion ratio
        completed = sum(1 for t in tasks if t.true_progress >= 1.0)
        completion_ratio = completed / total

        # Delay
        max_allowed_delay = self._state.max_days * 0.2   # 20% buffer allowed
        delay_penalty = min(1.0, self._state.total_delay_days / max(1, max_allowed_delay))

        # Budget
        budget_overrun = max(0.0, self._state.total_cost - self._state.total_budget)
        budget_score = max(0.0, 1.0 - (budget_overrun / max(1, self._state.total_budget)))

        # Efficiency
        total_worker_days = self._state.step_count * self._workforce_module.total_workers
        # Rough productive days estimation
        idle_fraction = 1.0 - (completion_ratio * 0.9)  # approximate
        efficiency_score = max(0.0, 1.0 - idle_fraction)

        # Critical path
        on_time, total_critical = self._task_module.get_critical_tasks_on_time(
            self._state.current_day
        )
        critical_score = on_time / max(1, total_critical)

        if self._state.difficulty == "easy":
            score = (
                0.5 * completion_ratio
                + 0.3 * efficiency_score
                + 0.2 * (1 - delay_penalty)
            )
        elif self._state.difficulty == "medium":
            score = (
                0.4 * completion_ratio
                + 0.2 * critical_score
                + 0.2 * budget_score
                + 0.2 * (1 - delay_penalty)
            )
        else:  # hard
            score = (
                0.3 * completion_ratio
                + 0.2 * (1 - delay_penalty)
                + 0.2 * budget_score
                + 0.15 * efficiency_score
                + 0.15 * critical_score
            )

        return {
            "score": round(max(0.0, min(1.0, score)), 4),
            "breakdown": {
                "completion_ratio": round(completion_ratio, 4),
                "delay_penalty": round(delay_penalty, 4),
                "budget_score": round(budget_score, 4),
                "efficiency_score": round(efficiency_score, 4),
                "critical_path_score": round(critical_score, 4),
            },
        }