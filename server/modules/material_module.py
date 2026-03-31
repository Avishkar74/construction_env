# server/modules/material_module.py
from __future__ import annotations
from typing import Dict, List
import random
from models import MaterialOrder


MATERIAL_COSTS = {
    "cement": 350.0,     # per unit (50kg bag)
    "steel":  2500.0,    # per unit (rod)
    "bricks": 8.0,       # per unit
    "timber": 450.0,     # per unit
    "paint":  120.0,     # per unit (litre)
    "tiles":  60.0,      # per unit
}

MATERIAL_SHELF_LIFE_DAYS = {
    "cement": 90,
    "paint": 365,
    "steel": 9999,
    "bricks": 9999,
    "timber": 180,
}


class MaterialModule:
    def __init__(self):
        self.inventory: Dict[str, float] = {}
        self.delivery_day: Dict[str, int] = {}
        self.material_costs: Dict[str, float] = dict(MATERIAL_COSTS)

    def initialize(self, starting_stock: Dict[str, float]):
        self.inventory = dict(starting_stock)
        self.delivery_day = {}
        self.material_costs = dict(MATERIAL_COSTS)

    def place_order(self, material_type: str, quantity: float, current_day: int, difficulty: str) -> MaterialOrder:
        # Delivery delay is stochastic
        delay_range = {"easy": (1, 3), "medium": (2, 5), "hard": (3, 8)}[difficulty]
        arrival_day = current_day + random.randint(*delay_range)
        cost = self.material_costs.get(material_type, 100.0) * quantity
        return MaterialOrder(
            material_type=material_type,
            quantity=quantity,
            arrival_day=arrival_day,
            cost=cost,
        )

    def process_deliveries(self, pending_orders: List[MaterialOrder], current_day: int) -> tuple:
        """Delivers due orders. Returns (remaining_orders, total_cost_of_new_orders)."""
        still_pending = []
        for order in pending_orders:
            if order.arrival_day <= current_day:
                self.inventory[order.material_type] = (
                    self.inventory.get(order.material_type, 0) + order.quantity
                )
                self.delivery_day[order.material_type] = current_day
            else:
                still_pending.append(order)
        return still_pending

    def update_material_costs(self, material_costs: Dict[str, float]) -> None:
        self.material_costs.update(material_costs)

    def get_cement_quality(self, current_day: int) -> float:
        delivered = self.delivery_day.get("cement", current_day)
        days_stored = current_day - delivered
        threshold = MATERIAL_SHELF_LIFE_DAYS["cement"]
        alpha = 0.005
        return max(0.0, 1.0 - (alpha * max(0, days_stored - threshold)))

    def age_inventory(self, current_day: int) -> List[str]:
        spoiled: List[str] = []
        for mat, qty in list(self.inventory.items()):
            shelf_life = MATERIAL_SHELF_LIFE_DAYS.get(mat, 9999)
            if shelf_life >= 9999 or qty <= 0:
                continue
            delivered = self.delivery_day.get(mat, current_day)
            days_stored = current_day - delivered
            if days_stored <= shelf_life:
                continue
            loss = qty * 0.10
            if loss > 0:
                self.inventory[mat] = max(0.0, qty - loss)
                spoiled.append(f"{mat}_spoiled:{loss:.1f}")
        return spoiled

    def get_inventory_snapshot(self) -> Dict[str, float]:
        return dict(self.inventory)