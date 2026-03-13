from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import BaseModel, Field


class BOMRow(BaseModel):
    si_no: int = Field(..., alias="SI.No")
    reference: str
    value: str
    footprint: str
    manufacturer_part_number: str | None = Field(None, alias="Manufacturer_Part_Number")
    manufacturer_name: str | None = Field(None, alias="Manufacturer_Name")
    manufacturer_part_number_lcsc: str | None = Field(None, alias="Manufacturer_Part_Number_LCSC")
    manufacturer_name_lcsc: str | None = Field(None, alias="Manufacturer_Name_LCSC")
    lcsc_sku_code: str | None = Field(None, alias="LCSC SKU code")
    qty: int
    dnp: bool | int = Field(False, alias="DNP")

    class Config:
        allow_population_by_field_name = True


class Project(BaseModel):
    name: str
    bom: List[BOMRow] = []

    def save(self, path: Path) -> None:
        path.write_text(self.json(indent=2))

    @classmethod
    def load(cls, path: Path) -> "Project":
        return cls.parse_raw(path.read_text())


class MasterItem(BaseModel):
    internal_id: str
    value: str
    footprint: str
    total_required_qty: int = 0
    current_stock: int = 0
    to_order: int = 0
    used_in_projects: List[str] = []
    associated_mpns: List[str] = []


class MasterInventory(BaseModel):
    items: List[MasterItem] = []

    def save(self, path: Path) -> None:
        path.write_text(self.json(indent=2))

    @classmethod
    def load(cls, path: Path) -> "MasterInventory":
        if not path.exists():
            return cls()
        return cls.parse_raw(path.read_text())
