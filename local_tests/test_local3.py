"""Detailed demo runner for ConstructionEnvironment

Run this script to produce verbose logs showing how the environment
behaves step-by-step. It includes two modes:
- client: uses the remote `ConstructionEnv` client (simulates user-facing API)
- direct: instantiates `ConstructionEnvironment` locally and prints internal state

Usage:
    python test_local_demo.py --mode both --difficulty easy --steps 20 --seed 0

The output is intentionally verbose for sharing with others.
"""
import argparse
import pprint
import time
from typing import List

from client import ConstructionEnv
from models import ConstructionAction


def print_tasks(tasks: List):
    for t in tasks:
        print(f"    - id={t.task_id:2d} | prog={t.progress:.3f} | assigned={t.assigned_workers:2d} | required={t.required_workers:2d} | blocked={t.blocked} | priority={t.priority} | start={t.planned_start} end={t.planned_end}")


def client_demo(steps: int, difficulty: str, seed: int, verbose: bool = True):
    print(f"\n=== CLIENT DEMO (difficulty={difficulty}, steps={steps}, seed={seed}) ===")
    with ConstructionEnv(base_url="https://avishkar-00-construction-env.hf.space").sync() as env:
        obs = env.reset(difficulty=difficulty)
        print("Initial observation (client):")
        print(f"  day={obs.observation.day} / max_days={obs.observation.max_days}")
        print(f"  workers_available={obs.observation.workers_available} / total_workers={obs.observation.total_workers}")
        print(f"  budget_used={obs.observation.budget_used:.3f} | pending_orders={len(obs.observation.pending_orders)}")
        print("  tasks:")
        print_tasks(obs.observation.tasks)

        cumulative = 0.0
        for step in range(1, steps + 1):
            # Simple demo policy (not optimal): allocate to highest-priority unblocked unfinished task
            target = None
            for t in obs.observation.tasks:
                if not t.blocked and t.progress < 1.0 and t.assigned_workers < t.required_workers:
                    target = t
                    break

            if target:
                action = ConstructionAction(action_type="allocate_workers", task_id=target.task_id, worker_count=min(obs.observation.workers_available, target.required_workers))
                action_desc = f"allocate_workers(task={target.task_id},count={action.worker_count})"
            else:
                action = ConstructionAction(action_type="do_nothing")
                action_desc = "do_nothing"

            if verbose:
                print(f"\n[Client] Step {step:02d} | Day {obs.observation.day:02d} | Action: {action_desc}")
                print(f"  before: workers_avail={obs.observation.workers_available} | budget_used={obs.observation.budget_used:.3f}")
                print("  tasks snapshot:")
                print_tasks(obs.observation.tasks)

            obs = env.step(action)
            r = obs.reward or 0.0
            cumulative += r

            print(f"  -> reward={r:+.4f} | cumulative={cumulative:+.4f} | workers_avail={obs.observation.workers_available} | pending_orders={len(obs.observation.pending_orders)}")
            if verbose:
                print(f"  after tasks snapshot:")
                print_tasks(obs.observation.tasks)

            if obs.done:
                print("Episode finished (obs.done=True)")
                break

        print(f"\nClient demo finished: cumulative reward={cumulative:.4f}")


def direct_demo(steps: int, difficulty: str, seed: int, verbose: bool = True):
    print(f"\n=== DIRECT DEMO (difficulty={difficulty}, steps={steps}, seed={seed}) ===")
    # Import here to avoid circular imports when running as client-only
    from server.construction_env_environment import ConstructionEnvironment

    env = ConstructionEnvironment()
    obs = env.reset(difficulty=difficulty)

    print("Initial internal state:")
    print(f"  state.current_day={env.state.current_day} | max_days={env.state.max_days}")
    print(f"  total_workers={env._workforce_module.total_workers} | workers_available={env._workers_available}")
    print(f"  total_cost={env._state.total_cost} | pending_orders={len(env._state.pending_orders)}")

    cumulative = 0.0
    for step in range(1, steps + 1):
        # Choose action: allocate to first unblocked unfinished task, else order material for blocked task
        target = None
        for t in env._task_module.tasks.values():
            if not t.blocked and t.true_progress < 1.0:
                target = t
                break

        if target is not None:
            action = ConstructionAction(action_type="allocate_workers", task_id=target.task_id, worker_count=env._workforce_module.total_workers)
            action_desc = f"allocate_workers(task={target.task_id},count={env._workforce_module.total_workers})"
        else:
            # try to order for first blocked task
            blocked_tasks = [t for t in env._task_module.tasks.values() if t.blocked]
            if blocked_tasks:
                b = blocked_tasks[0]
                mat = next(iter(b.required_materials.keys()))
                action = ConstructionAction(action_type="order_material", material_type=mat, quantity=10.0)
                action_desc = f"order_material({mat})"
            else:
                action = ConstructionAction(action_type="do_nothing")
                action_desc = "do_nothing"

        if verbose:
            print(f"\n[Direct] Step {step:02d} | Day {env.state.current_day} | Action: {action_desc}")
            # print true internal progress
            for t in env._task_module.tasks.values():
                print(f"    [INT] id={t.task_id:2d} | true_prog={t.true_progress:.3f} | assigned={t.assigned_workers} | blocked={t.blocked}")
            print(f"    workers_available={env._workers_available} | total_cost={env._state.total_cost}")

        obs = env.step(action)
        r = obs.reward or 0.0
        cumulative += r

        print(f"  -> reward={r:+.4f} | cumulative={cumulative:+.4f} | day={obs.day} | workers_avail={env._workers_available}")

        if obs.done:
            print("Episode finished (done)")
            break

    print(f"\nDirect demo finished: cumulative reward={cumulative:.4f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["client", "direct", "both"], default="both")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], default="easy")
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    # seed Python RNG for reproducibility
    import random
    random.seed(args.seed)

    if args.mode in ("client", "both"):
        client_demo(args.steps, args.difficulty, args.seed, verbose=True)
    if args.mode in ("direct", "both"):
        direct_demo(args.steps, args.difficulty, args.seed, verbose=True)


if __name__ == "__main__":
    main()
