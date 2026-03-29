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
import sys
from typing import List

from client import ConstructionEnv
from models import ConstructionAction

# Global logger function; will be set in `main()` to write to the output file.
def _default_log(*args, sep=' ', end='\n', console=True):
    # fallback to standard print if not initialized
    print(*args, sep=sep, end=end)

LOG = _default_log


def print_tasks(tasks: List):
    for t in tasks:
        # Support both TaskObservation (client-facing) and internal Task objects
        task_id = getattr(t, "task_id", None)
        progress = getattr(t, "progress", getattr(t, "true_progress", 0.0))
        assigned = getattr(t, "assigned_workers", 0)
        required = getattr(t, "required_workers", 0)
        blocked = getattr(t, "blocked", False)
        priority = getattr(t, "priority", "")
        start = getattr(t, "planned_start_day", getattr(t, "planned_start", None))
        end = getattr(t, "planned_end_day", getattr(t, "planned_end", None))
        LOG(
            f"    - id={task_id} | prog={progress:.3f} | assigned={assigned} | required={required} | blocked={blocked} | priority={priority} | start={start} end={end}"
        )


def client_demo(steps: int, difficulty: str, seed: int, verbose: bool = True):
    LOG(f"\n=== CLIENT DEMO (difficulty={difficulty}, steps={steps}, seed={seed}) ===")
    # Use localhost address for client connections on Windows
    with ConstructionEnv(base_url="http://127.0.0.1:8000").sync() as env:
        obs = env.reset(difficulty=difficulty)
        LOG("Initial observation (client):")
        LOG(f"  day={obs.observation.day} / max_days={obs.observation.max_days}")
        LOG(f"  workers_available={obs.observation.workers_available} / total_workers={obs.observation.total_workers}")
        LOG(f"  budget_used={obs.observation.budget_used:.3f} | pending_orders={len(obs.observation.pending_orders)}")
        LOG("  tasks:")
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
                LOG(f"\n[Client] Step {step:02d} | Day {obs.observation.day:02d} | Action: {action_desc}")
                LOG(f"  before: workers_avail={obs.observation.workers_available} | budget_used={obs.observation.budget_used:.3f}")
                LOG("  tasks snapshot:")
                print_tasks(obs.observation.tasks)

            obs = env.step(action)
            r = obs.reward or 0.0
            cumulative += r

            LOG(f"  -> reward={r:+.4f} | cumulative={cumulative:+.4f} | workers_avail={obs.observation.workers_available} | pending_orders={len(obs.observation.pending_orders)}")
            if verbose:
                LOG(f"  after tasks snapshot:")
                print_tasks(obs.observation.tasks)

            if obs.done:
                LOG("Episode finished (obs.done=True)")
                break

        LOG(f"\nClient demo finished: cumulative reward={cumulative:.4f}")


def direct_demo(steps: int, difficulty: str, seed: int, verbose: bool = True):
    LOG(f"\n=== DIRECT DEMO (difficulty={difficulty}, steps={steps}, seed={seed}) ===")
    # Import here to avoid circular imports when running as client-only
    from server.construction_env_environment import ConstructionEnvironment

    env = ConstructionEnvironment()
    obs = env.reset(difficulty=difficulty)

    LOG("Initial internal state:")
    LOG(f"  state.current_day={env.state.current_day} | max_days={env.state.max_days}")
    LOG(f"  total_workers={env._workforce_module.total_workers} | workers_available={env._workers_available}")
    LOG(f"  total_cost={env._state.total_cost} | pending_orders={len(env._state.pending_orders)}")

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
            LOG(f"\n[Direct] Step {step:02d} | Day {env.state.current_day} | Action: {action_desc}")
            # print true internal progress
            for t in env._task_module.tasks.values():
                LOG(f"    [INT] id={t.task_id:2d} | true_prog={t.true_progress:.3f} | assigned={t.assigned_workers} | blocked={t.blocked}")
            LOG(f"    workers_available={env._workers_available} | total_cost={env._state.total_cost}")

        obs = env.step(action)
        r = obs.reward or 0.0
        cumulative += r

        LOG(f"  -> reward={r:+.4f} | cumulative={cumulative:+.4f} | day={obs.day} | workers_avail={env._workers_available}")

        if obs.done:
            LOG("Episode finished (done)")
            break

    LOG(f"\nDirect demo finished: cumulative reward={cumulative:.4f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["client", "direct", "both"], default="both")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], default="easy")
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=str, default="test_local_demo_output.txt", help="Path to write demo output")
    args = parser.parse_args()

    # seed Python RNG for reproducibility
    import random
    random.seed(args.seed)

    # open output file and set LOG to write there with timestamps
    out_path = getattr(args, 'out', 'test_local_demo_output.txt')
    out_fh = open(out_path, 'w', encoding='utf-8')

    original_print = print

    def _log(*args, sep=' ', end='\n', console=True):
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        text = sep.join(map(str, args)) + end
        # prefix timestamp on each line of text
        for line in text.splitlines(True):
            out_fh.write(f"[{ts}] {line}")
        out_fh.flush()
        if console:
            original_print(*args, sep=sep, end=end)

    # set global LOG
    global LOG
    LOG = _log

    if args.mode in ("client", "both"):
        client_demo(args.steps, args.difficulty, args.seed, verbose=True)
    if args.mode in ("direct", "both"):
        direct_demo(args.steps, args.difficulty, args.seed, verbose=True)

    out_fh.close()


if __name__ == "__main__":
    main()
