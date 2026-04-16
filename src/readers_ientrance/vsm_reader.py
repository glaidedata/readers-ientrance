import pandas as pd
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional
import numpy as np


# A Pydantic schema to strictly define the reader's output
class VSMData(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    step: Optional[np.ndarray] = None
    iteration: Optional[np.ndarray] = None
    segment: Optional[np.ndarray] = None
    magnetic_field: Optional[np.ndarray] = None
    magnetic_moment: Optional[np.ndarray] = None
    time_stamp: Optional[np.ndarray] = None
    field_status: Optional[np.ndarray] = None
    moment_status: Optional[np.ndarray] = None

    # Fix for the Pydantic V2 warning
    model_config = ConfigDict(arbitrary_types_allowed=True)


def read_lakeshore_vsm(file_path: str) -> VSMData:
    """Reads a Lake Shore VSM CSV file and returns a strictly typed Pydantic model."""
    metadata = {}
    data_arrays = {}
    data_start_line = 0
    capture_next_line_as_software_version = False

    # --- 1. Extract Metadata ---
    with open(file_path, encoding="utf-8-sig", errors="ignore") as f:
        for i, line in enumerate(f):
            clean_line = line.strip()

            if clean_line.startswith("##DATA TABLE"):
                data_start_line = i + 1
                break

            if capture_next_line_as_software_version:
                metadata["Software Version"] = clean_line
                capture_next_line_as_software_version = False
                continue

            if "#RUN ON SOFTWARE VERSION" in clean_line:
                capture_next_line_as_software_version = True
                continue

            if ":" in clean_line and not clean_line.startswith("#"):
                key, value = clean_line.split(":", 1)
                metadata[key.strip()] = value.strip()

            if "#HYSTERESIS MEASUREMENT" in clean_line:
                metadata["Measurement Type"] = "HYSTERESIS"
            elif "#FORC MEASUREMENT" in clean_line:
                metadata["Measurement Type"] = "FORC"

    # --- 2. Extract Data Arrays ---
    df = pd.read_csv(file_path, skiprows=data_start_line, skipinitialspace=True)
    df.columns = df.columns.str.strip()

    col_mapping = {
        "Step": "step",
        "Iteration": "iteration",
        "Segment": "segment",
        "Field [Oe]": "magnetic_field",
        "Moment (m) [emu]": "magnetic_moment",
        "Time Stamp [s]": "time_stamp",
        "Field Status": "field_status",
        "Moment (m) Status": "moment_status",
    }

    for csv_col, dict_key in col_mapping.items():
        if csv_col in df.columns:
            if df[csv_col].dtype == object:
                data_arrays[dict_key] = df[csv_col].astype(str).str.strip().to_numpy()
            else:
                data_arrays[dict_key] = df[csv_col].to_numpy()

    return VSMData(metadata=metadata, **data_arrays)
