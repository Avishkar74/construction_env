# server/modules/workforce_module.py
"""
Workforce Module

Fixes vs original:
  - Recovery rate corrected (RECOVERY_PER_REST_DAY = 0.15, not 0.05)
  - Overtime cost charges only workers_on_task, not all workers
  - Efficiency formula unchanged
"""


class WorkforceModule:
    MAX_EFFICIENCY = 1.4
    MIN_EFFICIENCY = 0.6
    FATIGUE_PER_OVERTIME_HOUR = 0.05
    RECOVERY_PER_ACTIVE_DAY = 0.02   # small passive recovery even when working
    RECOVERY_PER_REST_DAY = 0.15     # significant recovery on low-activity days

    def __init__(self, total_workers: int):
        self.total_workers = total_workers
        self.efficiency = 1.0
        self.fatigue = 0.0
        self.overtime_approved_this_step = False

    def apply_overtime(self, hours: int) -> None:
        self.overtime_approved_this_step = True
        self.fatigue = min(1.0, self.fatigue + self.FATIGUE_PER_OVERTIME_HOUR * max(0, hours))
        # Short-term efficiency boost
        self.efficiency = min(self.MAX_EFFICIENCY, self.efficiency + 0.05)

    def end_of_day(self, workers_used: int) -> None:
        self.overtime_approved_this_step = False
        utilisation = workers_used / max(1, self.total_workers)
        if utilisation < 0.5:
            self.fatigue = max(0.0, self.fatigue - self.RECOVERY_PER_REST_DAY)
        else:
            self.fatigue = max(0.0, self.fatigue - self.RECOVERY_PER_ACTIVE_DAY)
        self.efficiency = max(
            self.MIN_EFFICIENCY, 1.0 - (self.fatigue * 0.4)
        )

    def overtime_cost(
        self, overtime_hours: int, workers_on_task: int | None = None
    ) -> float:
        """Charge only the workers who actually worked overtime."""
        count = workers_on_task if workers_on_task is not None else self.total_workers
        return max(0, count) * max(0, overtime_hours) * 200.0  # ₹200/worker/hr

    def daily_labor_cost(self, workers_used: int) -> float:
        return max(0, workers_used) * 800.0  # ₹800/worker/day base rate
