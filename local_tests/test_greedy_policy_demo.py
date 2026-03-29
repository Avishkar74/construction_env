"""Greedy policy demo

Allocates all available workers to the highest-priority unfinished critical-path task each step.
Logs per-step reward components and reports whether any positive per-step rewards occurred.

Usage:
    python test_greedy_policy_demo.py --steps 30 --difficulty medium --seed 1 --out greedy_output.txt
    python test_greedy_policy_demo.py --steps 30 --difficulty medium --seed 1 --out greedy_overtime.txt --overtime
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


def run_greedy_demo(steps: int, difficulty: str, seed: int, out_path: str, use_overtime: bool = False):
    LOG, close = make_logger(out_path)
    LOG(f"Greedy Policy Demo | difficulty={difficulty} | steps={steps} | seed={seed} | overtime={use_overtime}")

    random.seed(seed)
    env = ConstructionEnvironment()
    obs = env.reset(seed=seed, difficulty=difficulty)

    LOG("\nInitial snapshot:")
    LOG(f"  day={obs.day} | workers_available={obs.workers_available} | total_workers={obs.total_workers} | tasks={len(obs.tasks)}")

    cumulative = 0.0
    positive_steps = 0
    max_reward = -999.0
    rewards_list: List[float] = []

    for step in range(1, max(1, steps) + 1):
        # choose highest-priority unfinished critical task, else highest priority overall
        target = None
        # prefer critical path
        for t in obs.tasks:
            if t.is_critical_path and t.progress < 1.0:
                target = t
                break
        if target is None:
            for t in obs.tasks:
                if t.progress < 1.0:
                    target = t
                    break

        if target and obs.workers_available > 0:
            # allocate all available workers
            count = obs.workers_available
            action = ConstructionAction(action_type="allocate_workers", task_id=target.task_id, worker_count=count)
            action_desc = f"allocate_workers(task={target.task_id},count={count})"
        else:
            action = ConstructionAction(action_type="do_nothing")
            action_desc = "do_nothing"

        if use_overtime and target is not None:
            # approve overtime for the target in same step (costly)
            ot_action = ConstructionAction(action_type="approve_overtime", task_id=target.task_id, overtime_hours=4)
            # apply overtime first
            pre_workers = obs.workers_available
            obs_ot = env.step(ot_action)
            # then allocate
            obs = env.step(action)
            r = obs.reward or 0.0
            cumulative += r
        else:
            pre_workers = obs.workers_available
            obs = env.step(action)
            r = obs.reward or 0.0
            cumulative += r

        rewards_list.append(r)
        if r > 0:
            positive_steps += 1
        max_reward = max(max_reward, r)

        LOG(f"\nSTEP {step:02d} | Day {obs.day:02d} | Action: {action_desc}")
        LOG(f"  reward={r:+.4f} | cumulative={cumulative:+.4f} | workers_available={obs.workers_available}")
        if getattr(obs, 'reward_components', None) is not None:
            LOG(f"  reward_components={obs.reward_components}")
        if getattr(obs, 'active_issues', None) is not None:
            LOG(f"  active_issues={obs.active_issues}")

        if obs.done:
            LOG("Episode finished (done)")
            break

    avg_reward = sum(rewards_list) / max(1, len(rewards_list))
    LOG("\n=== Summary ===")
    LOG(f"Positive steps: {positive_steps} / {len(rewards_list)} | max_reward={max_reward:+.4f} | avg_reward={avg_reward:+.4f} | cumulative={cumulative:+.4f}")

    close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--difficulty", choices=["easy","medium","hard"], default="medium")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=str, default="greedy_output.txt")
    parser.add_argument("--overtime", action="store_true", help="Approve overtime before allocating")
    args = parser.parse_args()

    run_greedy_demo(args.steps, args.difficulty, args.seed, args.out, use_overtime=args.overtime)


if __name__ == "__main__":
    main()
