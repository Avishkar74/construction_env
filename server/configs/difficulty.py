# server/configs/difficulty.py
from typing import Dict, List, Any


def get_task_config(difficulty: str) -> List[Dict[str, Any]]:
    """Returns task list for each difficulty. Each task is a dict of Task constructor args."""

    easy = [
        {
            "task_id": 1, "title": "Site Preparation", "description": "Clear and level the site",
            "planned_start": 1, "planned_end": 5, "dependencies": [],
            "required_workers": 4, "required_materials": {"cement": 0},
            "is_critical_path": True, "priority": "high",
        },
        {
            "task_id": 2, "title": "Foundation", "description": "Pour concrete foundation",
            "planned_start": 6, "planned_end": 14, "dependencies": [1],
            "required_workers": 6, "required_materials": {"cement": 10, "steel": 5},
            "is_critical_path": True, "priority": "critical",
        },
        {
            "task_id": 3, "title": "Walls", "description": "Construct load-bearing walls",
            "planned_start": 15, "planned_end": 25, "dependencies": [2],
            "required_workers": 5, "required_materials": {"bricks": 50, "cement": 8},
            "is_critical_path": True, "priority": "critical",
        },
        {
            "task_id": 4, "title": "Roof", "description": "Install roofing structure",
            "planned_start": 26, "planned_end": 32, "dependencies": [3],
            "required_workers": 4, "required_materials": {"timber": 20, "steel": 8},
            "is_critical_path": True, "priority": "high",
        },
        {
            "task_id": 5, "title": "Finishing", "description": "Interior finishing and paint",
            "planned_start": 33, "planned_end": 40, "dependencies": [4],
            "required_workers": 3, "required_materials": {"paint": 30},
            "is_critical_path": False, "priority": "medium",
        },
    ]

    medium = easy + [
        {
            "task_id": 6, "title": "Electrical Rough-In", "description": "Install wiring conduits",
            "planned_start": 14, "planned_end": 26, "dependencies": [2],
            "required_workers": 3, "required_materials": {},
            "is_critical_path": False, "priority": "high",
        },
        {
            "task_id": 7, "title": "Plumbing", "description": "Install pipes and drainage",
            "planned_start": 14, "planned_end": 28, "dependencies": [2],
            "required_workers": 3, "required_materials": {},
            "is_critical_path": False, "priority": "medium",
        },
        {
            "task_id": 8, "title": "Windows & Doors", "description": "Install frames and fixtures",
            "planned_start": 22, "planned_end": 32, "dependencies": [3],
            "required_workers": 3, "required_materials": {},
            "is_critical_path": False, "priority": "medium",
        },
        {
            "task_id": 9, "title": "Electrical Fitting", "description": "Install switches, sockets, panels",
            "planned_start": 30, "planned_end": 40, "dependencies": [6, 7],
            "required_workers": 2, "required_materials": {},
            "is_critical_path": False, "priority": "high",
        },
        {
            "task_id": 10, "title": "Final Inspection", "description": "Walkthrough and punch-list",
            "planned_start": 42, "planned_end": 50, "dependencies": [4, 5, 7, 9],
            "required_workers": 2, "required_materials": {},
            "is_critical_path": True, "priority": "critical",
        },
    ]

    # Hard: 18 tasks with tight dependencies and budget
    hard = medium + [
        {
            "task_id": 11, "title": "HVAC Installation", "description": "Heating and cooling systems",
            "planned_start": 22, "planned_end": 36, "dependencies": [2],
            "required_workers": 3, "required_materials": {},
            "is_critical_path": False, "priority": "high",
        },
        {
            "task_id": 12, "title": "Insulation", "description": "Wall and roof insulation",
            "planned_start": 28, "planned_end": 38, "dependencies": [4],
            "required_workers": 2, "required_materials": {},
            "is_critical_path": False, "priority": "medium",
        },
        {
            "task_id": 13, "title": "Flooring", "description": "Tile and floor finishing",
            "planned_start": 38, "planned_end": 46, "dependencies": [7, 12],
            "required_workers": 3, "required_materials": {},
            "is_critical_path": False, "priority": "medium",
        },
        {
            "task_id": 14, "title": "Landscaping", "description": "Garden and external works",
            "planned_start": 42, "planned_end": 52, "dependencies": [8],
            "required_workers": 3, "required_materials": {},
            "is_critical_path": False, "priority": "low",
        },
        {
            "task_id": 15, "title": "Security Systems", "description": "CCTV and access control",
            "planned_start": 44, "planned_end": 52, "dependencies": [9],
            "required_workers": 2, "required_materials": {},
            "is_critical_path": False, "priority": "low",
        },
        {
            "task_id": 16, "title": "Elevator Installation", "description": "Lift system and shaft",
            "planned_start": 20, "planned_end": 40, "dependencies": [3],
            "required_workers": 4, "required_materials": {"steel": 15},
            "is_critical_path": True, "priority": "critical",
        },
        {
            "task_id": 17, "title": "Fire Safety", "description": "Sprinklers and alarms",
            "planned_start": 40, "planned_end": 52, "dependencies": [11, 16],
            "required_workers": 2, "required_materials": {},
            "is_critical_path": True, "priority": "critical",
        },
        {
            "task_id": 18, "title": "Commissioning", "description": "All systems test and handover",
            "planned_start": 53, "planned_end": 60, "dependencies": [10, 13, 17],
            "required_workers": 3, "required_materials": {},
            "is_critical_path": True, "priority": "critical",
        },
    ]

    configs = {"easy": easy, "medium": medium, "hard": hard}
    return configs.get(difficulty, medium)


DIFFICULTY_SETTINGS = {
    "easy": {
        "total_workers": 20,
        "total_budget": 800_000.0,
        "max_days": 50,
        "starting_materials": {"cement": 200, "steel": 100, "bricks": 500, "timber": 80, "paint": 60},
    },
    "medium": {
        "total_workers": 15,
        "total_budget": 600_000.0,
        "max_days": 60,
        "starting_materials": {"cement": 120, "steel": 60, "bricks": 300, "timber": 50, "paint": 40},
    },
    "hard": {
        "total_workers": 12,
        "total_budget": 450_000.0,
        "max_days": 65,
        "starting_materials": {"cement": 80, "steel": 40, "bricks": 200, "timber": 30, "paint": 20},
    },
}