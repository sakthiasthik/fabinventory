"""BOM file parsing for CSV and Excel formats"""

import pandas as pd
from pathlib import Path
from typing import List, Optional, Dict, Any
from src.models import BomRow


class BOMParser:
    """Parses BOM files in CSV or Excel format"""
    
    COLUMN_ALIASES = {
        "si_no": ["si.no", "s.no", "no", "index"],
        "reference": ["reference", "ref", "designator"],
        "value": ["value", "component value"],
        "footprint": ["footprint", "package"],
        "manufacturer_part_number": ["manufacturer_part_number", "mpn", "part number"],
        "manufacturer_name": ["manufacturer_name", "manufacturer", "brand"],
        "manufacturer_part_number_lcsc": ["manufacturer_part_number_lcsc"],
        "manufacturer_name_lcsc": ["manufacturer_name_lcsc"],
        "lcsc_sku": ["lcsc sku code", "lcsc", "sku"],
        "qty": ["qty", "quantity"],
        "dnp": ["dnp", "do not populate"]
    }
    
    @staticmethod
    def normalize_column(col):
        return col.strip().lower().replace(" ", "").replace("_", "")


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
            df_raw = pd.read_excel(file_path, engine='openpyxl', header=None)

            # Find header row (where "Reference" exists)
            header_row = None

            for i, row in df_raw.iterrows():
                row_values = [str(cell).lower() for cell in row.values]
                if any("reference" in cell for cell in row_values):
                    header_row = i
                    break

            if header_row is None:
                raise ValueError("Could not detect BOM header row")

            # Reload with correct header
            df = pd.read_excel(file_path, engine='openpyxl', header=header_row)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        # Validate required columns
        # Normalize dataframe columns
        df.columns = [col.strip() for col in df.columns]

        mapped_columns = {}

        for std_key, aliases in cls.COLUMN_ALIASES.items():
            for col in df.columns:
                norm_col = cls.normalize_column(col)
                if any(cls.normalize_column(alias) == norm_col for alias in aliases):
                    mapped_columns[std_key] = col
                    break

        # Only enforce minimal required fields
        required_fields = ["reference", "qty"]
        missing = [field for field in required_fields if field not in mapped_columns]

        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        # Parse rows
        bom_rows = []

        for idx, row in df.iterrows():
            try:
                def get(field, default=None):
                    col = mapped_columns.get(field)
                    return row[col] if col and pd.notna(row[col]) else default

                dnp_value = get("dnp", False)
                is_dnp = str(dnp_value).lower() in ['yes', 'true', 'x', '1']

                qty = int(get("qty", 0))

                bom_row = BomRow(
                    si_no=int(get("si_no", idx + 1)),
                    reference=str(get("reference", "")),
                    value=str(get("value", "")),
                    footprint=str(get("footprint", "")),
                    manufacturer_part_number=str(get("manufacturer_part_number", "")),
                    manufacturer_name=str(get("manufacturer_name", "")),
                    manufacturer_part_number_lcsc=str(get("manufacturer_part_number_lcsc", "")),
                    manufacturer_name_lcsc=str(get("manufacturer_name_lcsc", "")),
                    lcsc_sku=str(get("lcsc_sku", "")),
                    qty=qty,
                    dnp=is_dnp
                )

                bom_rows.append(bom_row)

            except Exception as e:
                print(f"Warning: Error parsing row {idx}: {e}")
                continue
        
        return bom_rows