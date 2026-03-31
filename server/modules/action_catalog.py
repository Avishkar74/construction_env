"""
Action catalog loader and cost calculator for extended construction actions.
"""
from __future__ import annotations

from dataclasses import dataclass
import ast
import json
import os
from typing import Dict, List, Optional


DEFAULT_ACTION_VARS: Dict[str, float] = {
    "A": 1500.0,
    "V": 50.0,
    "L": 100.0,
    "N": 1.0,
    "D": 1.0,
    "W": 4.0,
    "C": 1.0,
    "Q": 1.0,
    "F": 1.0,
    "T": 1.0,
    "R": 1.2,
    "S": 1.0,
    "E": 8000.0,
    "P": 5000.0,
    "OT": 0.0,
}


@dataclass
class ActionDefinition:
    name: str
    category: str
    phase: str
    prerequisites: List[str]
    enables: List[str]
    typical_duration_days: float
    min_workers: float
    max_workers: float
    cost_model: Dict


class ActionCatalog:
    def __init__(self, actions: Dict[str, ActionDefinition]):
        self._actions = actions

    @classmethod
    def load(cls, path: str) -> "ActionCatalog":
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        actions: Dict[str, ActionDefinition] = {}
        for entry in payload.get("actions", []):
            name = entry.get("name")
            if not name:
                continue
            actions[name] = ActionDefinition(
                name=name,
                category=entry.get("category", "meta"),
                phase=entry.get("phase", "operations"),
                prerequisites=list(entry.get("prerequisites", [])),
                enables=list(entry.get("enables", [])),
                typical_duration_days=float(entry.get("typical_duration_days", 1)),
                min_workers=float(entry.get("min_workers", 1)),
                max_workers=float(entry.get("max_workers", entry.get("min_workers", 1))),
                cost_model=dict(entry.get("cost_model", {})),
            )
        return cls(actions)

    @property
    def names(self) -> List[str]:
        return list(self._actions.keys())

    def definitions(self) -> List[ActionDefinition]:
        return list(self._actions.values())

    def get(self, name: str) -> Optional[ActionDefinition]:
        return self._actions.get(name)

    def available_actions(self, completed: List[str]) -> List[str]:
        completed_set = set(completed)
        available = []
        for action in self._actions.values():
            if all(req in completed_set for req in action.prerequisites):
                available.append(action.name)
        return available

    def compute_cost(self, action: ActionDefinition, variables: Dict[str, float]) -> float:
        model = action.cost_model or {}
        formula = str(model.get("formula", "0")).strip()
        base_rate = float(model.get("base_rate", 0.0) or 0.0)
        contingency_pct = float(model.get("contingency_pct", 0.0) or 0.0)

        cost = 0.0
        if formula and formula not in ("0", "nil", "none"):
            try:
                cost = _safe_eval(formula, variables)
            except Exception:
                cost = 0.0

        if cost <= 0.0 and base_rate > 0.0:
            cost = base_rate * max(1.0, variables.get("D", 1.0))

        if contingency_pct > 0:
            cost *= 1.0 + (contingency_pct / 100.0)

        return max(0.0, float(cost))

    @staticmethod
    def build_variables(
        action: ActionDefinition,
        overrides: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        values = dict(DEFAULT_ACTION_VARS)
        values["D"] = max(1.0, float(action.typical_duration_days or 1))
        values["W"] = max(1.0, float(action.min_workers or 1))
        values["OT"] = 0.0

        env_overrides = _load_env_overrides()
        values.update(env_overrides)
        if overrides:
            values.update(overrides)
        return values


def _load_env_overrides() -> Dict[str, float]:
    overrides: Dict[str, float] = {}
    for key in DEFAULT_ACTION_VARS.keys():
        env_key = f"ACTION_{key}"
        if env_key in os.environ:
            try:
                overrides[key] = float(os.environ[env_key])
            except ValueError:
                continue
    return overrides


def _safe_eval(expr: str, variables: Dict[str, float]) -> float:
    tree = ast.parse(expr, mode="eval")
    return float(_eval_node(tree.body, variables))


def _eval_node(node: ast.AST, variables: Dict[str, float]) -> float:
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left ** right
        raise ValueError("unsupported operator")
    if isinstance(node, ast.UnaryOp):
        value = _eval_node(node.operand, variables)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return value
        raise ValueError("unsupported unary")
    if isinstance(node, ast.Num):
        return float(node.n)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("unsupported constant")
    if isinstance(node, ast.Name):
        return float(variables.get(node.id, 1.0))
    raise ValueError("unsupported expression")
