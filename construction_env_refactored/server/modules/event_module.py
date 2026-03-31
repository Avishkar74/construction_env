# server/modules/event_module.py
"""
Event Module — All stochastic disruptions.

Events implemented:
  - Weather roll
  - Worker absence
  - Equipment failure/degradation
  - Material delivery delay
  - Quality rework (progress regression)
  - Price escalation (hard mode)
"""
from __future__ import annotations
import random
from typing import Dict, List, Tuple


WEATHER_PROBS: Dict[str, Dict[str, float]] = {
    "easy":   {"clear": 0.80, "rain": 0.18, "storm": 0.02},
    "medium": {"clear": 0.65, "rain": 0.28, "storm": 0.07},
    "hard":   {"clear": 0.50, "rain": 0.33, "storm": 0.17},
}

WEATHER_MODIFIERS: Dict[str, float] = {
    "clear": 1.0,
    "rain": 0.65,
    "storm": 0.20,
}


class EventModule:
    def __init__(self, difficulty: str = "medium"):
        self.difficulty = difficulty

    def roll_weather(self) -> Tuple[str, float]:
        probs = WEATHER_PROBS[self.difficulty]
        weather = random.choices(
            list(probs.keys()), weights=list(probs.values()), k=1
        )[0]
        return weather, WEATHER_MODIFIERS[weather]

    def roll_worker_absence(self, total_workers: int) -> Tuple[int, List[str]]:
        issues: List[str] = []
        lost = 0
        prob = {"easy": 0.05, "medium": 0.15, "hard": 0.25}[self.difficulty]
        if random.random() < prob:
            lost = random.randint(1, max(1, total_workers // 5))
            issues.append(f"worker_absent:{lost}")
        return lost, issues

    def roll_equipment_failure(
        self, equipment_health: Dict[str, float]
    ) -> Tuple[Dict[str, float], List[str]]:
        issues: List[str] = []
        fail_prob = {"easy": 0.02, "medium": 0.06, "hard": 0.12}[self.difficulty]
        for equip in list(equipment_health.keys()):
            if random.random() < fail_prob:
                equipment_health[equip] = max(
                    0.1, equipment_health[equip] - 0.2
                )
                issues.append(f"equipment_degraded:{equip}")
        return equipment_health, issues

    def roll_material_delivery_delay(
        self, pending_orders: list
    ) -> Tuple[list, List[str]]:
        """In-transit orders may be delayed further."""
        issues: List[str] = []
        prob = {"easy": 0.03, "medium": 0.08, "hard": 0.15}[self.difficulty]
        updated = []
        for order in pending_orders:
            if random.random() < prob:
                extra = random.randint(1, 3)
                order.arrival_day += extra
                issues.append(
                    f"material_delay:{order.material_type}:{extra}d"
                )
            updated.append(order)
        return updated, issues

    def roll_quality_rework(self, tasks: dict) -> Tuple[dict, List[str]]:
        """Random quality failure causing progress regression."""
        issues: List[str] = []
        prob = {"easy": 0.02, "medium": 0.05, "hard": 0.10}[self.difficulty]
        for task in tasks.values():
            if 0.3 < task.true_progress < 0.9 and random.random() < prob:
                setback = random.uniform(0.05, 0.15)
                task.true_progress = max(0.0, task.true_progress - setback)
                task.rework_count += 1
                issues.append(f"rework:{task.task_id}:{setback:.2f}")
        return tasks, issues

    def roll_price_escalation(
        self, material_costs: Dict[str, float]
    ) -> Tuple[Dict[str, float], List[str]]:
        """Occasional material price spikes (hard mode only)."""
        issues: List[str] = []
        if self.difficulty == "hard" and random.random() < 0.05:
            mat = random.choice(["steel", "cement"])
            spike = random.uniform(1.05, 1.20)
            material_costs[mat] = material_costs.get(mat, 1.0) * spike
            issues.append(f"price_spike:{mat}:{spike:.2f}x")
        return material_costs, issues
