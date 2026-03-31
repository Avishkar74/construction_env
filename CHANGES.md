# CHANGES.md — Refactored Construction RL Environment

## Summary of All Fixes (v8 refactor)

This document maps every critical issue from the original codebase to its fix.

---

## 🔴 CRITICAL FIXES (P0)

### FIX 1 — `bad_action` never set to True
**File:** `server/construction_env_environment.py`  
**Original bug:** `bad_action = False` was initialized but never changed.  
The `-1.5` reward penalty was dead code — agent was never penalized for invalid allocations.  
**Fix:** `bad_action = True` is now set when:
- `task is None` (non-existent task ID)
- `task.blocked or task.true_progress >= 1.0` (allocating to finished/blocked task)
- `worker_count <= 0` (zero-worker allocation)

---

### FIX 2 — Budget ratio stale when computing reward
**File:** `server/construction_env_environment.py`  
**Original bug:** `budget_ratio` was computed BEFORE order costs were added to `total_cost`.  
Reward function saw an under-estimate → under-penalised expensive ordering.  
**Fix:** `total_cost` is accumulated first, then `budget_ratio` is computed fresh before reward.

---

### FIX 3 — Linear worker scaling (overstates progress on large crews)
**File:** `server/modules/task_module.py`  
**Original bug:** `base_gain = 0.02 * self.assigned_workers` — linear.  
Trained agent to dump all workers on one task. In reality, crowding kills productivity.  
**Fix:** Crowding-aware model:
```python
n_opt = self.required_workers
above_opt = max(0, assigned - n_opt)
crowd_factor = max(0.4, 1.0 - 0.10 * above_opt)
effective = min(assigned, n_opt) + above_opt * crowd_factor
base_gain = 0.02 * effective
```

---

### FIX 4 — Equipment health unused in progress calculation
**File:** `server/modules/task_module.py`  
**Original bug:** Equipment health tracked, degrades via EventModule, but never applied to `update_progress`.  
**Fix:** `equipment_health` parameter added to `update_progress`. Modifier applied:
```python
equip_key = EQUIPMENT_DEPENDENT_TASKS.get(self.title)
if equip_key:
    equip_modifier = max(0.4, equipment_health.get(equip_key, 1.0))
```
Also passed through `update_all()` and called correctly from `construction_env_environment.py`.

---

## 🟠 HIGH PRIORITY FIXES (P1)

### FIX 5 — Weather applies equally to indoor and outdoor tasks
**File:** `server/modules/task_module.py`  
**Original bug:** Storm weather penalized indoor tasks (electrical fitting, tiling, painting).  
Agent was punished for making the correct decision to work indoors.  
**Fix:** `_effective_weather_modifier()` method:
- Concrete tasks: `0.0` in rain/storm (cannot pour)
- Outdoor tasks: apply `weather_modifier`
- All other (indoor) tasks: always `1.0`

---

### FIX 6 — Auto-reschedule doesn't preserve task duration
**File:** `server/construction_env_environment.py`  
**Original bug:** `_auto_reschedule_ready_tasks` updated `planned_start` but not `planned_end`.  
Created phantom `days_behind_schedule` values.  
**Fix:**
```python
original_duration = task.planned_end - task.planned_start
task.planned_start = current_day
task.planned_end = current_day + original_duration
```

---

### FIX 7 — Hard mode missing material dependencies (8 of 9 tasks empty)
**File:** `server/configs/difficulty.py`  
**Original bug:** Tasks 11–18 had `required_materials: {}`. Material management was trivial at hard difficulty.  
**Fix:** Added realistic dependencies:
- Task 11 (HVAC): `{"steel": 5}`
- Task 12 (Insulation): `{"timber": 8}`
- Task 13 (Flooring): `{"cement": 3, "tiles": 40}`

---

## 🟡 MEDIUM PRIORITY FIXES (P2)

### FIX 8 — Fatigue recovery 4× too slow
**File:** `server/modules/workforce_module.py`  
**Original:** `RECOVERY_PER_REST_DAY = 0.05` → 20 rest days to fully recover.  
**Fix:** `RECOVERY_PER_REST_DAY = 0.15` → ~7 rest days (realistic).

---

### FIX 9 — Overtime charges all workers, not just assigned workers
**File:** `server/modules/workforce_module.py`  
**Original:** `return self.total_workers * overtime_hours * 200.0`  
**Fix:** `workers_on_task` parameter properly used.

---

### FIX 10 — Missing stochastic events (rework, delivery delay, price)
**File:** `server/modules/event_module.py`  
Added all three events from the original improvement notes:
- `roll_material_delivery_delay` — in-transit orders get delayed
- `roll_quality_rework` — progress regression for partially-complete tasks
- `roll_price_escalation` — material price spikes (hard mode)

---

### FIX 11 — Cement quality not exposed in observation
**File:** `server/construction_env_environment.py` + `models.py`  
Added `cement_quality: float` field to `ConstructionObservation`.  
Agent can now see degraded cement and make informed ordering decisions.

---

### FIX 12 — Material consumption logic (fragile mid-loop mutation)
**File:** `server/modules/task_module.py`  
Separated material checking from consumption into clean methods:
- `_check_materials()` → returns `(fully_ok, arriving, blocking)`
- `_consume_materials()` → called only when `fully_ok`

---

## 🟢 LOW PRIORITY FIXES (P3)

### FIX 13 — Material spoilage
**File:** `server/modules/material_module.py`  
Added `age_inventory()` method that degrades materials past shelf life by 10%/period.

### FIX 14 — Strategy v8 policy improvements
**File:** `policies/strategy_v8.py`
- Overtime approved for top-2 critical tasks (was top-1)
- Threshold lowered from 3 days to 2 days behind
- `_task_score` penalises already over-staffed tasks (`-30.0`)
- Prefetch uses `workers^0.85` for realistic day-estimate lookahead
- `tiles` added to medium/hard starting materials config

---

## 🔧 POST-REFACTOR FIXES

### FIX 15 — Prep work progress regression
**File:** `server/modules/task_module.py`  
**Issue:** Prep-work cap could reduce progress if a task was already past the cap.  
**Fix:** Prep work is clamped to never reduce progress.

### FIX 16 — Inference score alignment
**File:** `inference.py`  
**Issue:** Inference reported completion-only score.  
**Fix:** Inference now computes the same multi-objective score as the grader using state + tasks.

---

## File Inventory

| File | Status |
|------|--------|
| `models.py` | Updated: `cement_quality` field added to observation |
| `server/construction_env_environment.py` | Fixed: FIX 1,2,3,4,6 |
| `server/modules/task_module.py` | Fixed: FIX 3,4,5,12,15 |
| `server/modules/workforce_module.py` | Fixed: FIX 8,9 |
| `server/modules/material_module.py` | Fixed: FIX 13, cement quality |
| `server/modules/event_module.py` | Fixed: FIX 10 |
| `server/modules/chat_module.py` | Unchanged |
| `server/configs/difficulty.py` | Fixed: FIX 7 |
| `policies/strategy_v8.py` | New: FIX 14 |
| `inference.py` | Updated: uses v8 policy, aligned scoring (FIX 16) |
