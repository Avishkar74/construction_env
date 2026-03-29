# test_local.py  — run from inside construction_env/ directory
import sys, os
sys.path.insert(0, os.path.abspath("."))

from client import ConstructionEnv
from models import ConstructionAction

BASE_URL = "https://avishkar-00-construction-env.hf.space"

def test_easy():
    print("\n=== Testing EASY difficulty ===")
    with ConstructionEnv(base_url=BASE_URL).sync() as env:
        # Reset with easy difficulty (deterministic seed)
        obs = env.reset(difficulty="easy", seed=0)
        print(f"Day {obs.observation.day}/{obs.observation.max_days} | Tasks: {len(obs.observation.tasks)} | Workers: {obs.observation.workers_available}/{obs.observation.total_workers}")
        print(f"Weather: {obs.observation.weather} | Budget used: {obs.observation.budget_used:.1%}")
        print(f"Chat: {obs.observation.chat_messages[0]}")

        step = 0
        total_reward = 0.0

        while not obs.done and step < 5:
            # Simple greedy policy: find first unblocked task, allocate all workers
            target_task = None
            for task in obs.observation.tasks:
                if not task.blocked and task.progress < 1.0 and task.assigned_workers < task.required_workers:
                    target_task = task
                    break

            if target_task:
                action = ConstructionAction(
                    action_type="allocate_workers",
                    task_id=target_task.task_id,
                    worker_count=obs.observation.workers_available,
                )
            else:
                action = ConstructionAction(action_type="do_nothing")

            obs = env.step(action)
            total_reward += obs.reward or 0
            step += 1
            print(f"Day {obs.observation.day} | Reward: {(obs.reward or 0):.3f} | "
                f"Progress: {sum(t.progress for t in obs.observation.tasks)/len(obs.observation.tasks):.1%}")

        print(f"Total reward after {step} steps: {total_reward:.3f}")
        print("✅ Easy test passed!")


def test_all_difficulties():
    for diff in ("easy", "medium", "hard"):
        print(f"\n=== Testing {diff.upper()} ===")
        with ConstructionEnv(base_url=BASE_URL).sync() as env:
            obs = env.reset(difficulty=diff, seed=0)
            assert obs.observation.day == 1, "Reset should start at day 1"
            assert len(obs.observation.tasks) > 0, "Should have tasks"
            assert obs.observation.workers_available > 0, "Should have workers"

            # Take one step
            action = ConstructionAction(action_type="do_nothing")
            obs2 = env.step(action)
            assert obs2.observation.day == 2, "Day should advance"

            print(f"  ✅ {diff}: {len(obs.observation.tasks)} tasks, {obs.observation.workers_available} workers, day advances correctly")


def test_material_order():
    print("\n=== Testing Material Order ===")
    with ConstructionEnv(base_url=BASE_URL).sync() as env:
        obs = env.reset(difficulty="medium", seed=0)
        cement_before = obs.observation.materials_available.get("cement", 0)

        action = ConstructionAction(
            action_type="order_material",
            material_type="cement",
            quantity=50.0,
        )
        obs2 = env.step(action)

        assert len(obs2.observation.pending_orders) > 0, "Order should be pending"
        print(f"  Cement before: {cement_before:.1f}, Pending orders: {len(obs2.observation.pending_orders)}")
        print("  ✅ Material order test passed!")


def test_worker_reset():
    """Verify workers are freed each step (Bug 1 fix verification)."""
    print("\n=== Testing Worker Reset Per Step ===")
    with ConstructionEnv(base_url=BASE_URL).sync() as env:
        obs = env.reset(difficulty="easy", seed=0)
        total = obs.observation.total_workers

        # Step 1: allocate all workers
        action = ConstructionAction(
            action_type="allocate_workers",
            task_id=1,
            worker_count=total,
        )
        obs = env.step(action)
        print(f"  After allocation step: workers_available = {obs.observation.workers_available}")

        # Step 2: do nothing — workers should be freed from tasks; global absences may reduce total
        obs = env.step(ConstructionAction(action_type="do_nothing"))
        tasks_ok = all(t.assigned_workers == 0 for t in obs.observation.tasks)
        assert tasks_ok, "Assigned workers should be released from tasks each step"
        assert 0 <= obs.observation.workers_available <= total, (
            f"Workers available should be between 0 and {total}, got {obs.observation.workers_available}"
        )
        print(f"  After do_nothing step: workers_available = {obs.observation.workers_available} (total={total})")
        print("  ✅ Worker reset test passed!")


if __name__ == "__main__":
    test_easy()
    test_all_difficulties()
    test_material_order()
    test_worker_reset()
    print("\n🎉 All tests passed!")