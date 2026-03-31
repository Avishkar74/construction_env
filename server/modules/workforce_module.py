# server/modules/workforce_module.py


class WorkforceModule:
    MAX_EFFICIENCY = 1.4
    MIN_EFFICIENCY = 0.6
    FATIGUE_PER_OVERTIME_HOUR = 0.05
    RECOVERY_PER_ACTIVE_DAY = 0.02
    RECOVERY_PER_REST_DAY = 0.15

    def __init__(self, total_workers: int):
        self.total_workers = total_workers
        self.efficiency = 1.0
        self.fatigue = 0.0
        self.overtime_approved_this_step = False

    def apply_overtime(self, hours: int):
        self.overtime_approved_this_step = True
        self.fatigue = min(1.0, self.fatigue + (self.FATIGUE_PER_OVERTIME_HOUR * max(0, hours)))
        # Short term boost, long term cost
        self.efficiency = min(self.MAX_EFFICIENCY, self.efficiency + 0.05)

    def end_of_day(self, workers_used: int):
        self.overtime_approved_this_step = False
        # Natural fatigue recovery on rest (unused workers)
        if workers_used < self.total_workers * 0.5:
            self.fatigue = max(0.0, self.fatigue - self.RECOVERY_PER_REST_DAY)
        else:
            self.fatigue = max(0.0, self.fatigue - self.RECOVERY_PER_ACTIVE_DAY)
        # Fatigue reduces efficiency
        self.efficiency = max(
            self.MIN_EFFICIENCY,
            1.0 - (self.fatigue * 0.4)
        )

    def overtime_cost(self, overtime_hours: int, workers_on_task: int | None = None) -> float:
        count = self.total_workers if workers_on_task is None else max(0, workers_on_task)
        return count * overtime_hours * 200.0  # ₹200/worker/hour

    def daily_labor_cost(self, workers_used: int) -> float:
        return workers_used * 800.0  # ₹800/worker/day base rate