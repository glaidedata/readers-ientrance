import pandas as pd
import numpy as np
import io
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional

# A Pydantic schema strictly defining the reader's output
class ThermalData(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    data: Optional[pd.DataFrame] = None
    
    # Extracted core arrays
    time_stamp: Optional[np.ndarray] = None
    comment: Optional[list] = None
    system_temperature: Optional[np.ndarray] = None
    field: Optional[np.ndarray] = None
    chamber_pres: Optional[np.ndarray] = None
    temperature_status: Optional[np.ndarray] = None
    field_status: Optional[np.ndarray] = None
    chamber_status: Optional[np.ndarray] = None
    bridge_cycle: Optional[np.ndarray] = None
    therm_resistance: Optional[np.ndarray] = None
    therm_resistance_rate: Optional[np.ndarray] = None
    field_rate: Optional[np.ndarray] = None
    cell_imbalance: Optional[np.ndarray] = None
    cell_imbalance_rate: Optional[np.ndarray] = None
    tap_imbalance: Optional[np.ndarray] = None
    coarse_dac_imbalance: Optional[np.ndarray] = None
    fine_dac_imbalance: Optional[np.ndarray] = None
    loop_imbalance: Optional[np.ndarray] = None
    sample_temperature: Optional[np.ndarray] = None
    sample_temperature_rate: Optional[np.ndarray] = None
    dilation: Optional[np.ndarray] = None
    dilation_rate: Optional[np.ndarray] = None
    rotator_angle: Optional[np.ndarray] = None
    sample_temperature_range: Optional[np.ndarray] = None
    therm_exp_coeff_raw: Optional[np.ndarray] = None
    therm_exp_coeff: Optional[np.ndarray] = None
    therm_exp_coeff_compare: Optional[np.ndarray] = None
    therm_exp_coeff_diff_percentage: Optional[np.ndarray] = None
    therm_exp_coeff_diff_absolute: Optional[np.ndarray] = None
    therm_exp_coeff_baseline: Optional[np.ndarray] = None
    therm_exp_coeff_reference: Optional[np.ndarray] = None

    # Allow DataFrames and NumPy arrays in Pydantic v2
    model_config = ConfigDict(arbitrary_types_allowed=True)

def read_thermal_dat(filepath: str) -> ThermalData:
    """Reads a Dilatometry/Thermal Analysis .dat file and returns a Pydantic model."""
    metadata = {}
    data_lines = []
    
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        
    data_start_idx = -1
    in_header = False
    
    # --- 1. Extract Top Header Metadata ---
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if line_stripped == "[Header]":
            in_header = True
            continue
        elif line_stripped == "[Data]":
            in_header = False
            data_start_idx = i + 1
            break
        elif in_header and line_stripped:
            parts = line_stripped.split(",", 1)
            if len(parts) == 2:
                metadata[parts[0].strip()] = parts[1].strip()

    if data_start_idx == -1:
        raise ValueError("Could not find [Data] section in the file.")

    # --- 2. Process Data Rows and Embedded Parameters ---
    columns_line = lines[data_start_idx].strip()
    columns = [c.strip() for c in columns_line.split(",")]
    
    in_params_block = False
    for line in lines[data_start_idx + 1:]:
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        parts = line_stripped.split(",")
        # The 'Comment' column is index 1, where the parameters live
        comment_field = parts[1] if len(parts) > 1 else ""
        
        if "BEGIN:PARAMS" in comment_field:
            in_params_block = True
            continue
        elif "END:PARAMS" in comment_field:
            in_params_block = False
            continue
            
        if in_params_block:
            # Parse parameters formatted as key=value
            if "=" in comment_field:
                key, val = comment_field.split("=", 1)
                metadata[key.strip()] = val.strip()
        else:
            # Collect standard data rows
            data_lines.append(line_stripped)

    # --- 3. Build DataFrame ---
    df = pd.read_csv(io.StringIO("\n".join(data_lines)), names=columns)
    
    # --- 4. Extract Core Data Arrays ---
    # Map raw CSV columns to Pydantic schema names
    col_mapping = {
        "TimeStamp (sec)": "time_stamp",
        "Comment": "comment",
        "System Temperature (K)": "system_temperature",
        "Field (Oe)": "field",
        "Chamber Pres (torr)": "chamber_pres",
        "Temperature Status (code)": "temperature_status",
        "Field Status (code)": "field_status",
        "Chamber Status (code)": "chamber_status",
        "Bridge Cycle (count)": "bridge_cycle",
        "Therm Resistance (ohms)": "therm_resistance",
        "Therm Resistance Rate (ohms/sec)": "therm_resistance_rate",
        "Field Rate (Oe/sec)": "field_rate",
        "Cell Imbalance (ppm)": "cell_imbalance",
        "Cell Imbalance Rate (ppm/sec)": "cell_imbalance_rate",
        "Tap Imbalance (ppm)": "tap_imbalance",
        "Coarse DAC Imbalance (ppm)": "coarse_dac_imbalance",
        "Fine DAC Imbalance (ppm)": "fine_dac_imbalance",
        "Loop Imbalance (ppm)": "loop_imbalance",
        "Sample Temperature (K)": "sample_temperature",
        "Sample Temperature Rate (K/sec)": "sample_temperature_rate",
        "Dilation (ppm)": "dilation",
        "Dilation Rate (ppm/sec)": "dilation_rate",
        "Rotator Angle (deg)": "rotator_angle",
        "Sample Temperature Range (K)": "sample_temperature_range",
        "Therm Exp Coeff Raw (ppm/K)": "therm_exp_coeff_raw",
        "Therm Exp Coeff (ppm/K)": "therm_exp_coeff",
        "Therm Exp Coeff Compare (ppm/K)": "therm_exp_coeff_compare",
        "Therm Expansion Coeff Diff (%)": "therm_exp_coeff_diff_percentage",
        "Therm Expansion Coeff Diff (abs)": "therm_exp_coeff_diff_absolute",
        "Therm Exp Coeff Baseline (ppm/K)": "therm_exp_coeff_baseline",
        "Therm Exp Coeff Reference (ppm/K)": "therm_exp_coeff_reference"
    }
    
    extracted_arrays = {}
    for csv_col, attr_name in col_mapping.items():
        if csv_col in df.columns:
            extracted_arrays[attr_name] = pd.to_numeric(df[csv_col], errors="coerce").to_numpy()
        else:
            extracted_arrays[attr_name] = None
            
    return ThermalData(
        metadata=metadata,
        data=df,
        **extracted_arrays
    )