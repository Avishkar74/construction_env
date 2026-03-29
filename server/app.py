# server/app.py
"""
FastAPI application for the Construction RL Environment.

Endpoints provided automatically by create_app:
    POST /reset      — Reset the environment (accepts difficulty kwarg)
    POST /step       — Execute one action (one day)
    GET  /state      — Current hidden state
    GET  /schema     — Action / observation JSON schemas
    WS   /ws         — WebSocket for persistent sessions

Custom endpoints added below:
    GET  /tasks      — All three difficulty task configs (for evaluation)
    GET  /grader     — Score the current episode
    GET  /health     — Health check

Usage:
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 2
"""

try:
    from openenv.core.env_server.http_server import create_app
except ImportError as e:
    raise ImportError(
        "openenv is required. Install with: pip install openenv-core"
    ) from e

# Support both installed-package and direct-run import paths
try:
    from construction_env.models import ConstructionAction, ConstructionObservation
    from construction_env.server.construction_env_environment import ConstructionEnvironment
except ModuleNotFoundError:
    
    from models import ConstructionAction, ConstructionObservation
    from server.construction_env_environment import ConstructionEnvironment

# ── Create the app (mirrors the pattern from openenv init) ──
app = create_app(
    ConstructionEnvironment,
    ConstructionAction,
    ConstructionObservation,
    env_name="construction_env",
    max_concurrent_envs=10,   # raise for production; keep low for HF free tier
)


# ── Custom endpoints ──

from fastapi.responses import JSONResponse


@app.get("/tasks")
async def list_tasks():
    """
    Return all three difficulty task configurations.
    Useful for evaluation scripts and judges who want to inspect task graphs.
    """
    try:
        from server.configs.difficulty import get_task_config, DIFFICULTY_SETTINGS
    except ModuleNotFoundError:
        from configs.difficulty import get_task_config, DIFFICULTY_SETTINGS

    return {
        "difficulties": {
            d: {
                "tasks": get_task_config(d),
                "settings": DIFFICULTY_SETTINGS[d],
            }
            for d in ("easy", "medium", "hard")
        }
    }


@app.get("/grader")
async def grader_info():
    """
    Explains how to retrieve the deterministic score for a completed episode.
    Scoring happens inside the environment instance via compute_score().

    In your client code, after the episode ends, call:
        score_data = env.compute_score()   # if you have a direct reference
    Or use the /state endpoint to inspect episode_id, then compute locally.
    """
    return JSONResponse(content={
        "info": (
            "After your episode ends (obs.done == True), call compute_score() "
            "on your ConstructionEnvironment instance to get a 0.0–1.0 score. "
            "The score breakdown includes: completion_ratio, delay_penalty, "
            "budget_score, efficiency_score, critical_path_score."
        ),
        "score_weights": {
            "easy":   {"completion": 0.5, "efficiency": 0.3, "delay": 0.2},
            "medium": {"completion": 0.4, "critical_path": 0.2, "budget": 0.2, "delay": 0.2},
            "hard":   {"completion": 0.3, "delay": 0.2, "budget": 0.2, "efficiency": 0.15, "critical_path": 0.15},
        },
    })


@app.get("/health")
async def health():
    return {"status": "healthy", "environment": "ConstructionEnvironment", "version": "1.0.0"}


# ── Direct execution entrypoint ──

def _run_uvicorn(host: str, port: int):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


def main():
    """Entry point for OpenEnv validation and package entrypoints.

    This function is a no-argument callable so validation tools and
    package entrypoints can import and call `main()` directly.
    """
    _run_uvicorn("0.0.0.0", 8000)


def cli():
    """CLI wrapper to run the server with optional arguments.

    Use `python -m server.app` or `python -m construction_env.server.app`.
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    _run_uvicorn("0.0.0.0", args.port)


if __name__ == "__main__":
    cli()