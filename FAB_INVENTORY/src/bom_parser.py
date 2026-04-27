"""BOM file parsing for CSV and Excel formats"""

import pandas as pd
from pathlib import Path
from typing import List, Optional, Dict, Any
from src.models import BomRow


class BOMParser:
    """Parses BOM files in CSV or Excel format"""
    
    COLUMN_MAPPING = {
        "SI.No": "si_no",
        "Reference": "reference",
        "Value": "value",
        "Footprint": "footprint",
        "Manufacturer_Part_Number": "manufacturer_part_number",
        "Manufacturer_Name": "manufacturer_name",
        "Manufacturer_Part_Number_LCSC": "manufacturer_part_number_lcsc",
        "Manufacturer_Name_LCSC": "manufacturer_name_lcsc",
        "LCSC SKU code": "lcsc_sku",
        "Qty": "qty",
        "DNP": "dnp"
    }
    
    @classmethod
    def parse_file(cls, file_path: str) -> List[BomRow]:
        """Parse BOM from CSV or Excel file"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read based on file extension
        if file_path.suffix.lower() in ['.csv']:
            df = pd.read_csv(file_path)
        elif file_path.suffix.lower() in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path, engine='openpyxl')
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        # Validate required columns
        required_columns = list(cls.COLUMN_MAPPING.keys())
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Parse rows
        bom_rows = []
        for idx, row in df.iterrows():
            try:
                # Handle DNP column
                dnp_value = row["DNP"]
                is_dnp = False
                if pd.notna(dnp_value):
                    if isinstance(dnp_value, bool):
                        is_dnp = dnp_value
                    elif isinstance(dnp_value, str):
                        is_dnp = dnp_value.lower() in ['yes', 'true', 'x', '1']
                    elif isinstance(dnp_value, (int, float)):
                        is_dnp = bool(dnp_value)
                
                # Parse quantity
                qty = 0
                if pd.notna(row["Qty"]):
                    qty = int(row["Qty"])
                
                bom_row = BomRow(
                    si_no=int(row["SI.No"]) if pd.notna(row["SI.No"]) else idx + 1,
                    reference=str(row["Reference"]) if pd.notna(row["Reference"]) else "",
                    value=str(row["Value"]) if pd.notna(row["Value"]) else "",
                    footprint=str(row["Footprint"]) if pd.notna(row["Footprint"]) else "",
                    manufacturer_part_number=str(row["Manufacturer_Part_Number"]) if pd.notna(row["Manufacturer_Part_Number"]) else "",
                    manufacturer_name=str(row["Manufacturer_Name"]) if pd.notna(row["Manufacturer_Name"]) else "",
                    manufacturer_part_number_lcsc=str(row["Manufacturer_Part_Number_LCSC"]) if pd.notna(row["Manufacturer_Part_Number_LCSC"]) else None,
                    manufacturer_name_lcsc=str(row["Manufacturer_Name_LCSC"]) if pd.notna(row["Manufacturer_Name_LCSC"]) else None,
                    lcsc_sku=str(row["LCSC SKU code"]) if pd.notna(row["LCSC SKU code"]) else None,
                    qty=qty,
                    dnp=is_dnp
                )
                
                bom_rows.append(bom_row)
            except Exception as e:
                print(f"Warning: Error parsing row {idx}: {e}")
                continue
        
        return bom_rows