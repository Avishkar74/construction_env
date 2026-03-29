# server/modules/chat_module.py
from __future__ import annotations
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..modules.task_module import TaskModule


class ChatModule:
    """Generates contextual PM advisor messages based on actual environment state."""

    def generate(
        self,
        current_day: int,
        max_days: int,
        task_module: "TaskModule",
        workers_available: int,
        total_workers: int,
        materials: dict,
        weather: str,
        budget_ratio: float,
        difficulty: str,
    ) -> List[str]:
        messages = []
        tasks = task_module.tasks

        # Time pressure
        days_left = max_days - current_day
        completion = sum(t.true_progress for t in tasks.values()) / max(1, len(tasks))
        if days_left < 15 and completion < 0.7:
            messages.append(
                f"Warning: Only {days_left} days left and project is {completion*100:.0f}% complete. Prioritize critical path tasks immediately."
            )

        # Idle workers
        if workers_available > total_workers * 0.4:
            messages.append(
                f"You have {workers_available} workers idle. Assign them to in-progress tasks to avoid paying idle wages."
            )

        # Blocked tasks
        blocked = [t for t in tasks.values() if t.blocked]
        if blocked:
            names = ", ".join(t.title for t in blocked[:2])
            messages.append(f"Tasks blocked: {names}. Check dependencies and material availability.")

        # Low material
        critical_low = [
            mat for mat, qty in materials.items()
            if qty < 20 and mat in ("cement", "steel")
        ]
        if critical_low:
            messages.append(
                f"Material alert: {', '.join(critical_low)} running low. Place orders now — delivery takes 2–5 days."
            )

        # Budget
        if budget_ratio > 0.80:
            messages.append(
                "Budget at 80%+. Avoid overtime. Consider descoping non-critical finishing tasks."
            )
        elif budget_ratio > 0.90:
            messages.append(
                "CRITICAL: Budget nearly exhausted. Any further overtime or orders risk project failure."
            )

        # Weather
        if weather == "storm":
            messages.append("Storm day. All outdoor work will be severely impacted. Reassign to indoor tasks.")
        elif weather == "rain":
            messages.append("Rain today. Outdoor progress will be slower. Consider moving workers indoors.")

        # Hard mode: conflicting guidance (makes the agent think)
        if difficulty == "hard" and len(messages) >= 2:
            import random
            if random.random() < 0.3:
                messages.append(
                    "Client update: Accelerate exterior work regardless of weather — deadline is firm."
                )

        return messages[:3] if messages else ["Project status nominal. Continue current allocation."]