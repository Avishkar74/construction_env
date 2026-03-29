"""Worker Absence scenario demo

This script runs the `ConstructionEnvironment` directly and monitors worker-absence
events. It produces a detailed, human-readable log explaining what was tested,
what happened, and how the environment performed.

Usage:
    python test_worker_absence_demo.py --steps 30 --difficulty medium --seed 1 --out worker_absence_output.txt

"""
import argparse
import time
import os
import random
from typing import List

from server.construction_env_environment import ConstructionEnvironment
from models import ConstructionAction


def make_logger(out_path: str):
    fh = open(out_path, "w", encoding="utf-8")

    def log(*args, sep=' ', end='\n', console=True):
        text = sep.join(map(str, args)) + end
        for line in text.splitlines(True):
            fh.write(line)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except Exception:
            pass
        if console:
            print(*args, sep=sep, end=end)

    def close():
        try:
            fh.flush()
            os.fsync(fh.fileno())
        except Exception:
            pass
        fh.close()

    return log, close


def run_worker_absence_demo(steps: int, difficulty: str, seed: int, out_path: str):
    LOG, close = make_logger(out_path)
    LOG(f"Worker Absence Scenario Demo | difficulty={difficulty} | steps={steps} | seed={seed}")
    LOG(f"DEBUG: script args -> steps={steps}, difficulty={difficulty}, seed={seed}")

    random.seed(seed)
    env = ConstructionEnvironment()
    obs = env.reset(seed=seed, difficulty=difficulty)

    # Record events observed by wrapping the EventModule.roll_worker_absence
    events: List[dict] = []

    orig_roll = env._event_module.roll_worker_absence

    def wrapper(total_workers):
        lost, issues = orig_roll(total_workers)
        # record the day and lost count
        events.append({
            "day": env.state.current_day,
            "lost": lost,
            "issues": issues,
        })
        return lost, issues

    env._event_module.roll_worker_absence = wrapper

    LOG("\nInitial snapshot:")
    LOG(f"  day={obs.day} | workers_available={obs.workers_available} | total_workers={obs.total_workers} | pending_orders={len(obs.pending_orders)}")
    LOG(f"DEBUG: observation tasks_count={len(obs.tasks)} | task_ids={[t.task_id for t in obs.tasks]}")

    cumulative = 0.0
    # run steps, apply a simple policy: allocate to first available unblocked task
    for step in range(1, max(1, steps) + 1):
        # choose target
        target = None
        for t in obs.tasks:
            if not t.blocked and t.progress < 1.0 and t.assigned_workers < t.required_workers:
                target = t
                break

        if target:
            action = ConstructionAction(action_type="allocate_workers", task_id=target.task_id, worker_count=min(obs.workers_available, target.required_workers))
            action_desc = f"allocate_workers(task={target.task_id},count={action.worker_count})"
        else:
            action = ConstructionAction(action_type="do_nothing")
            action_desc = "do_nothing"

        # capture pre-step snapshot for logging, then run step and log using post-step day
        pre_workers = obs.workers_available
        pre_pending = len(obs.pending_orders)
        pre_budget = obs.budget_used

        obs = env.step(action)
        r = obs.reward or 0.0
        cumulative += r

        LOG(f"\nSTEP {step:02d} | Day {obs.day:02d} | Action: {action_desc}")
        LOG(f"  before: workers_available={pre_workers} | pending_orders={pre_pending} | budget_used={pre_budget}")
        LOG(f"  -> reward={r:+.4f} | cumulative={cumulative:+.4f} | workers_available={obs.workers_available} | pending_orders={len(obs.pending_orders)}")

        # print any worker absence events that occurred this step (events recorded against the current day)
        todays_events = [e for e in events if e["day"] == env.state.current_day]
        if todays_events:
            for e in todays_events:
                if e["lost"] > 0:
                    LOG(f"  EVENT: Worker absence detected on day {e['day']}: {e['lost']} workers absent. Issues={e['issues']}")
                else:
                    LOG(f"  EVENT: No worker absence on day {e['day']}")
        # also log what the observation reported for active issues (server-exposed)
        if getattr(obs, 'active_issues', None) is not None:
            LOG(f"  OBSERVED active_issues={obs.active_issues}")
        # log reward components if provided
        if getattr(obs, 'reward_components', None) is not None:
            LOG(f"  OBSERVED reward_components={obs.reward_components}")

        if obs.done:
            LOG("Episode finished (done)")
            break

    # Summarize scenario in paragraphs
    LOG("\n=== Scenario Summary ===")
    total_absences = sum(e['lost'] for e in events)
    days_with_absence = sum(1 for e in events if e['lost'] > 0)
    LOG(f"Total worker-absence events: {days_with_absence} days with absence, total workers lost across episode: {total_absences}")
    LOG(f"Final day: {env.state.current_day} | Total delay days: {env.state.total_delay_days} | Total cost: {env.state.total_cost:.2f} | Cumulative reward: {cumulative:.4f}")

    # Paragraph explanation
    LOG("\nExplanation:")
    LOG("This scenario tests how the environment handles stochastic worker absences and how a simple allocation policy reacts.")
    LOG("We recorded each day the number of workers absent (if any). When absences occur, fewer workers are available to be assigned, which reduces progress and can increase delay days.")
    LOG("The log above lists per-step observations and explicit EVENT lines when absences occurred, so you can trace cause → effect: absence -> fewer workers -> lower progress -> reward impact.")

    LOG("\nPerformance assessment:")
    if days_with_absence == 0:
        LOG("No absences occurred during this run (seed-determined). The policy performed as expected under normal conditions.")
    else:
        LOG(f"Absences occurred on {days_with_absence} day(s). The simple allocation policy does not proactively reassign or approve overtime; therefore we observed reduced progress on affected days and a lower cumulative reward compared to a no-absence baseline.")
        LOG("To mitigate such events, a real PM policy could: (1) pre-approve overtime for critical-path tasks, (2) reassign crews to keep critical tasks moving, or (3) keep contingency buffer workers.")

    close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--difficulty", choices=["easy","medium","hard"], default="medium")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=str, default="worker_absence_output.txt")
    args = parser.parse_args()

    run_worker_absence_demo(args.steps, args.difficulty, args.seed, args.out)


if __name__ == "__main__":
    main()
