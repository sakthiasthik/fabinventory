from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field

@dataclass
class BomRow:
    si_no: int
    reference: str
    value: str
    footprint: str
    manufacturer_part_number: str
    manufacturer_name: str
    manufacturer_part_number_lcsc: Optional[str] = None
    manufacturer_name_lcsc: Optional[str] = None
    lcsc_sku: Optional[str] = None
    qty: int = 0
    dnp: bool = False
    
    def get_aggregation_key(self):
        return f"{self.value}|{self.footprint}"
    
    def is_active(self):
        return not self.dnp and self.qty > 0


@dataclass
class Project:
    name: str

    description: str = ""

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    updated_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    # ====================================
    # ELECTRICAL BOM
    # ====================================

    bom: List[BomRow] = field(default_factory=list)

    # ====================================
    # PROJECT IMAGE
    # ====================================

    image: str = ""

    
    model_3d_file: str = ""

    # ====================================
    # MECHANICAL BOM
    # ====================================

    mechanical_bom: Optional[str] = None

    # ====================================
    # PCB BOM
    # ====================================

    pcb_bom: Optional[str] = None

    pcb_gerber_zip: Optional[str] = None

    pcb_gerber_folder: Optional[str] = None

    pcb_repo_link: str = ""

    # ====================================
    # 3D PRINT BOM
    # ====================================

    print3d_bom: Optional[str] = None

@dataclass
class MasterItem:
    internal_id: str
    value: str
    footprint: str
    total_required: int = 0
    current_stock: int = 0
    used_in_projects: List[str] = field(default_factory=list)
    associated_mpns: List[str] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def to_order(self):
        return max(0, self.total_required - self.current_stock)
    
    def to_dict(self):
        return {
            "internal_id": self.internal_id,
            "value": self.value,
            "footprint": self.footprint,
            "total_required": self.total_required,
            "current_stock": self.current_stock,
            "used_in_projects": self.used_in_projects,
            "associated_mpns": self.associated_mpns,
            "last_updated": self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)

@dataclass
class OrderLineItem:
    internal_id: str
    qty_ordered: int
    unit_price: Optional[float] = None
    manufacturer_part_number: Optional[str] = None

@dataclass
class Order:
    order_id: str
    supplier: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"
    line_items: List[OrderLineItem] = field(default_factory=list)
    notes: Optional[str] = None
    received_at: Optional[str] = None
    
    @property
    def total_items(self):
        return sum(item.qty_ordered for item in self.line_items)

    @property
    def estimated_cost(self):
        # Simple placeholder logic
        return sum(
            getattr(item, "qty_ordered", 0) * 10  # assume ₹10 per item
            for item in self.line_items
        )
    
    def to_dict(self):
        return {
            "order_id": self.order_id,
            "supplier": self.supplier,
            "created_at": self.created_at,
            "status": self.status,
            "line_items": [
                {
                    "internal_id": item.internal_id,
                    "qty_ordered": item.qty_ordered,
                    "unit_price": item.unit_price,
                    "manufacturer_part_number": item.manufacturer_part_number
                }
                for item in self.line_items
            ],
            "notes": self.notes,
            "received_at": self.received_at
        }
    
    @classmethod
    def from_dict(cls, data):
        line_items = [OrderLineItem(**item) for item in data.get("line_items", [])]
        return cls(
            order_id=data["order_id"],
            supplier=data["supplier"],
            created_at=data.get("created_at", datetime.now().isoformat()),
            status=data.get("status", "pending"),
            line_items=line_items,
            notes=data.get("notes"),
            received_at=data.get("received_at")
        )

@dataclass
class Config:
    company_prefix: str
    repo_path: str = "./fabinventory_data"
    last_sync: Optional[str] = None