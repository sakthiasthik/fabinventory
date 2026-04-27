"""Inventory and order management"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from src.models import MasterItem, Order, OrderLineItem
from src.file_manager import FileManager
from src.aggregator import Aggregator


class InventoryManager:
    """Manages inventory and purchase orders"""
    
    def __init__(self, file_manager: FileManager, aggregator: Aggregator):
        self.file_manager = file_manager
        self.aggregator = aggregator
        self.inventory: List[MasterItem] = []
        self._load_inventory()
    
    def _load_inventory(self):
        self.inventory = self.file_manager.load_master_inventory()
        if self.inventory:
            max_id = 0
            for item in self.inventory:
                try:
                    id_num = int(item.internal_id.split('-')[-1])
                    max_id = max(max_id, id_num)
                except:
                    pass
            self.aggregator.set_next_id(max_id + 1)
    
    def update_inventory(self, projects) -> List[MasterItem]:
        existing_items = self.inventory if self.inventory else None
        self.inventory = self.aggregator.aggregate(projects, existing_items)
        self.file_manager.save_master_inventory(self.inventory)
        return self.inventory
    
    def update_stock(self, internal_id: str, new_stock: int) -> Optional[MasterItem]:
        for item in self.inventory:
            if item.internal_id == internal_id:
                item.current_stock = new_stock
                item.last_updated = datetime.now().isoformat()
                self.file_manager.save_master_inventory(self.inventory)
                return item
        return None
    
    def get_inventory(self) -> List[MasterItem]:
        return self.inventory
    
    def get_items_to_order(self) -> List[MasterItem]:
        return [item for item in self.inventory if item.to_order > 0]
    
    def create_order(self, supplier: str, items: List[Dict[str, Any]], notes: str = "") -> Optional[Order]:
        existing_orders = self.file_manager.list_orders()
        order_num = len(existing_orders) + 1
        order_id = f"PO-{datetime.now().strftime('%Y%m')}-{order_num:03d}"
        
        line_items = []
        for item_data in items:
            line_item = OrderLineItem(
                internal_id=item_data['internal_id'],
                qty_ordered=item_data['qty'],
                unit_price=item_data.get('unit_price'),
                manufacturer_part_number=item_data.get('mpn')
            )
            line_items.append(line_item)
        
        order = Order(
            order_id=order_id,
            supplier=supplier,
            line_items=line_items,
            notes=notes
        )
        
        if self.file_manager.save_order(order):
            return order
        return None
    
    def receive_order(self, order_id: str) -> bool:
        order = self.file_manager.load_order(order_id)
        if not order or order.status != "pending":
            return False
        
        for line_item in order.line_items:
            for inventory_item in self.inventory:
                if inventory_item.internal_id == line_item.internal_id:
                    inventory_item.current_stock += line_item.qty_ordered
                    inventory_item.last_updated = datetime.now().isoformat()
                    break
        
        order.status = "received"
        order.received_at = datetime.now().isoformat()
        
        self.file_manager.save_master_inventory(self.inventory)
        self.file_manager.save_order(order)
        return True
    
    def get_order_summary(self) -> Dict[str, Any]:
        orders = self.file_manager.list_orders()
        
        pending_orders = [o for o in orders if o.status == "pending"]
        received_orders = [o for o in orders if o.status == "received"]
        
        total_pending_items = sum(o.total_items for o in pending_orders)
        total_received_items = sum(o.total_items for o in received_orders)
        
        supplier_summary = {}
        for order in pending_orders:
            if order.supplier not in supplier_summary:
                supplier_summary[order.supplier] = {
                    'orders': [],
                    'total_items': 0,
                    'estimated_cost': 0
                }
            supplier_summary[order.supplier]['orders'].append(order)
            supplier_summary[order.supplier]['total_items'] += order.total_items
            if order.estimated_cost:
                supplier_summary[order.supplier]['estimated_cost'] += order.estimated_cost
        
        return {
            'total_orders': len(orders),
            'pending_orders': len(pending_orders),
            'received_orders': len(received_orders),
            'total_pending_items': total_pending_items,
            'total_received_items': total_received_items,
            'supplier_summary': supplier_summary,
            'pending_orders_list': pending_orders,
            'received_orders_list': received_orders
        }
    
    def get_inventory_summary(self) -> Dict[str, Any]:
        items_to_order = self.get_items_to_order()
        
        footprint_counts = {}
        for item in self.inventory:
            if item.footprint not in footprint_counts:
                footprint_counts[item.footprint] = 0
            footprint_counts[item.footprint] += 1
        
        return {
            'total_components': len(self.inventory),
            'total_required': sum(item.total_required for item in self.inventory),
            'total_stock': sum(item.current_stock for item in self.inventory),
            'total_to_order': sum(item.to_order for item in self.inventory),
            'components_to_order': len(items_to_order),
            'footprint_distribution': footprint_counts
        }