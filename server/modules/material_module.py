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
}


class MaterialModule:
    def __init__(self):
        self.inventory: Dict[str, float] = {}

    def initialize(self, starting_stock: Dict[str, float]):
        self.inventory = dict(starting_stock)

    def place_order(self, material_type: str, quantity: float, current_day: int, difficulty: str) -> MaterialOrder:
        # Delivery delay is stochastic
        delay_range = {"easy": (1, 3), "medium": (2, 5), "hard": (3, 8)}[difficulty]
        arrival_day = current_day + random.randint(*delay_range)
        cost = MATERIAL_COSTS.get(material_type, 100.0) * quantity
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
            else:
                still_pending.append(order)
        return still_pending

    def get_inventory_snapshot(self) -> Dict[str, float]:
        return dict(self.inventory)