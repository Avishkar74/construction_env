# server/modules/event_module.py
from __future__ import annotations
import random
from typing import List, Dict, Tuple


WEATHER_PROBS = {
    "easy":   {"clear": 0.80, "rain": 0.18, "storm": 0.02},
    "medium": {"clear": 0.65, "rain": 0.28, "storm": 0.07},
    "hard":   {"clear": 0.50, "rain": 0.33, "storm": 0.17},
}

WEATHER_MODIFIERS = {
    "clear": 1.0,
    "rain": 0.65,
    "storm": 0.20,
}


class EventModule:
    def __init__(self, difficulty: str = "medium"):
        self.difficulty = difficulty
        self.issues: List[str] = []

    def roll_weather(self) -> Tuple[str, float]:
        probs = WEATHER_PROBS[self.difficulty]
        weather = random.choices(
            list(probs.keys()), weights=list(probs.values()), k=1
        )[0]
        return weather, WEATHER_MODIFIERS[weather]

    def roll_worker_absence(self, total_workers: int) -> Tuple[int, List[str]]:
        """Returns (workers_lost, issues)."""
        issues = []
        lost = 0
        if self.difficulty == "easy":
            prob = 0.05
        elif self.difficulty == "medium":
            prob = 0.15
        else:
            prob = 0.25

        if random.random() < prob:
            lost = random.randint(1, max(1, total_workers // 5))
            issues.append(f"worker_absent:{lost}")
        return lost, issues

    def roll_equipment_failure(self, equipment_health: Dict[str, float]) -> Tuple[Dict[str, float], List[str]]:
        issues = []
        fail_prob = {"easy": 0.02, "medium": 0.06, "hard": 0.12}[self.difficulty]
        for equip in equipment_health:
            if random.random() < fail_prob:
                equipment_health[equip] = max(0.1, equipment_health[equip] - 0.2)
                issues.append(f"equipment_degraded:{equip}")
        return equipment_health, issues