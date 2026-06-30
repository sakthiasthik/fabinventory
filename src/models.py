from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass, field
import dataclasses
import re

# Project names: alphanumeric, dash, underscore. 1-64 chars. No dots, slashes, or special chars.
PROJECT_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$')

def validate_project_name(name: str) -> str:
    """Validate and return a project name, or raise ValueError."""
    if not PROJECT_NAME_RE.match(name):
        raise ValueError(
            f"Invalid project name: '{name}'. "
            "Use 1-64 letters, numbers, dashes, or underscores."
        )
    return name

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
    dnp_raw: str = ""
    
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

    pcb_image: Optional[str] = None

    pcb_gerber_folder: Optional[str] = None

    pcb_repo_link: str = ""

    github_links: List[Dict] = field(default_factory=list)

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
        # Filter to only known fields to survive version changes
        valid_keys = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

@dataclass
class OrderLineItem:
    internal_id: str
    qty_ordered: int
    unit_price: Optional[float] = None
    manufacturer_part_number: Optional[str] = None

@dataclass
class Order:
    # Order status constants
    STATUS_DRAFT = "draft"
    STATUS_ORDERED = "ordered"
    STATUS_SHIPPED = "shipped"
    STATUS_RECEIVED = "received"
    STATUS_CANCELLED = "cancelled"

    # Valid state transitions
    VALID_TRANSITIONS = {
        STATUS_DRAFT: {STATUS_ORDERED, STATUS_CANCELLED},
        STATUS_ORDERED: {STATUS_SHIPPED, STATUS_CANCELLED},
        STATUS_SHIPPED: {STATUS_RECEIVED, STATUS_CANCELLED},
        STATUS_RECEIVED: set(),                    # terminal
        STATUS_CANCELLED: set(),                   # terminal
    }

    order_id: str
    supplier: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = STATUS_DRAFT
    line_items: List[OrderLineItem] = field(default_factory=list)
    notes: Optional[str] = None
    received_at: Optional[str] = None
    shipped_at: Optional[str] = None
    tracking_info: Optional[str] = None
    shipping_info: Optional[str] = None

    def can_transition_to(self, new_status: str) -> bool:
        """Check if transitioning to new_status is allowed."""
        return new_status in self.VALID_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status: str) -> bool:
        """Transition to new_status. Returns True if successful, False if invalid."""
        if not self.can_transition_to(new_status):
            return False
        self.status = new_status
        if new_status == self.STATUS_RECEIVED:
            self.received_at = datetime.now().isoformat()
        elif new_status == self.STATUS_SHIPPED:
            self.shipped_at = datetime.now().isoformat()
        return True

    @property
    def total_items(self):
        return sum(item.qty_ordered for item in self.line_items)

    @property
    def estimated_cost(self):
        return sum(
            (item.unit_price or 0) * item.qty_ordered
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
            "received_at": self.received_at,
            "shipped_at": self.shipped_at,
            "tracking_info": self.tracking_info,
            "shipping_info": self.shipping_info
        }

    @classmethod
    def from_dict(cls, data):
        line_items = [OrderLineItem(**item) for item in data.get("line_items", [])]
        return cls(
            order_id=data["order_id"],
            supplier=data["supplier"],
            created_at=data.get("created_at", datetime.now().isoformat()),
            status=data.get("status", cls.STATUS_DRAFT),
            line_items=line_items,
            notes=data.get("notes"),
            received_at=data.get("received_at"),
            shipped_at=data.get("shipped_at"),
            tracking_info=data.get("tracking_info"),
            shipping_info=data.get("shipping_info")
        )

@dataclass
class Supplier:
    """Supplier information for purchase orders."""
    name: str
    contact: str = ""
    email: str = ""
    website: str = ""
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            "name": self.name,
            "contact": self.contact,
            "email": self.email,
            "website": self.website,
            "notes": self.notes,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data["name"],
            contact=data.get("contact", ""),
            email=data.get("email", ""),
            website=data.get("website", ""),
            notes=data.get("notes", ""),
            created_at=data.get("created_at", "")
        )


@dataclass
class Config:
    company_prefix: str
    repo_path: str = "./fabinventory_data"
    last_sync: Optional[str] = None