import pandas as pd
import numpy as np
import io
import re
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional, List

# Pydantic schema strictly defining the DSC output
class DSCData(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    method_steps: List[str] = Field(default_factory=list)
    data: Optional[pd.DataFrame] = None

    # Core Arrays mapped from the columns
    time: Optional[np.ndarray] = None
    unsubtracted_heat_flow: Optional[np.ndarray] = None
    baseline_heat_flow: Optional[np.ndarray] = None
    program_temperature: Optional[np.ndarray] = None
    sample_temperature: Optional[np.ndarray] = None
    approx_gas_flow: Optional[np.ndarray] = None
    calibration: Optional[np.ndarray] = None
    heat_flow: Optional[np.ndarray] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

def read_perkinelmer_dsc(filepath: str) -> DSCData:
    """Reads a PerkinElmer DSC .txt file and returns a structured Pydantic model."""
    metadata = {}
    method_steps = []
    data_lines = []

    state = "TOP_METADATA"
    last_key = None
    current_section = ""

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        original_line = line
        line = line.strip()

        if not line:
            if state == "DATA":
                state = "BOTTOM_METADATA"
            continue

        # --- STATE: Top Metadata ---
        if state == "TOP_METADATA":
            if "Method Steps:" in line:
                state = "METHOD_STEPS"
                continue

            if ":" in line:
                key, val = line.split(":", 1)
                key, val = key.strip(), val.strip()
                if key:
                    full_key = f"{current_section}_{key}" if current_section else key
                    metadata[full_key] = val
                    last_key = full_key
            elif last_key == "Comment":
                metadata[last_key] += f"\n{line}"
            elif not "\t" in line and len(line) < 40:
                current_section = line.strip()

        # --- STATE: Method Steps ---
        elif state == "METHOD_STEPS":
            if line == "Time" or line.startswith("Time\t"):
                state = "DATA_HEADERS"
                continue
            method_steps.append(line)

        # --- STATE: Data Headers ---
        elif state == "DATA_HEADERS":
            clean_parts = original_line.split()
            if len(clean_parts) > 3:
                try:
                    float(clean_parts[0].replace(',', '.'))
                    state = "DATA"
                except ValueError:
                    pass
            if state != "DATA":
                continue

        # --- STATE: Raw Data Rows ---
        if state == "DATA":
            clean_parts = original_line.split()
            is_numeric = False
            if len(clean_parts) > 3:
                try:
                    float(clean_parts[0].replace(',', '.'))
                    is_numeric = True
                except ValueError:
                    pass

            if is_numeric:
                data_lines.append(original_line.strip())
                continue
            else:
                # Non-numeric line -> transition to footer and fall through!
                state = "BOTTOM_METADATA"

        # --- STATE: Bottom Metadata / Footer ---
        if state == "BOTTOM_METADATA":
            if line.endswith(":") and (line.isupper() or "CALIBRATION" in line.upper() or "PROFILE" in line.upper()):
                raw_section = line[:-1].strip()
                # Dynamically strip specific instrument names (e.g. "DSC8500 ") so schemas don't break
                current_section = re.sub(r'^DSC\d+\s*', '', raw_section)
                continue

            if ":" in line:
                key, val = line.split(":", 1)
                full_key = f"{current_section}_{key.strip()}" if current_section else f"Footer_{key.strip()}"
                metadata[full_key] = val.strip()
            elif "=" in line:
                parts = line.split("=", 1)
                if len(parts) == 2:
                    full_key = f"{current_section}_{parts[0].strip()}" if current_section else f"Footer_{parts[0].strip()}"
                    metadata[full_key] = parts[1].strip()
            elif "\t" in line:
                parts = line.split("\t", 1)
                if len(parts) == 2 and parts[0].strip():
                    full_key = f"{current_section}_{parts[0].strip()}" if current_section else f"Footer_{parts[0].strip()}"
                    metadata[full_key] = parts[1].strip()
            else:
                # Fallback for double-spaced keys
                parts = re.split(r'\s{2,}', line, maxsplit=1)
                if len(parts) == 2 and parts[0].strip():
                    full_key = f"{current_section}_{parts[0].strip()}" if current_section else f"Footer_{parts[0].strip()}"
                    metadata[full_key] = parts[1].strip()

    # --- Process Data into DataFrame and Arrays ---
    columns = [
        "time",
        "unsubtracted_heat_flow",
        "baseline_heat_flow",
        "program_temperature",
        "sample_temperature",
        "approx_gas_flow",
        "calibration",
        "heat_flow"
    ]

    df = pd.DataFrame()
    extracted_arrays = {col: None for col in columns}

    if data_lines:
        try:
            # Try strict tab separation first
            df = pd.read_csv(io.StringIO("\n".join(data_lines)), sep="\t", header=None)
            if len(df.columns) < 4:
                # Fallback to whitespace separation if tabs fail
                df = pd.read_csv(io.StringIO("\n".join(data_lines)), sep=r"\s+", header=None)
        except Exception:
            df = pd.read_csv(io.StringIO("\n".join(data_lines)), sep=r"\s+", header=None)

        num_cols = min(len(df.columns), len(columns))
        df = df.iloc[:, :num_cols]
        df.columns = columns[:num_cols]

        for col in df.columns:
            extracted_arrays[col] = pd.to_numeric(df[col], errors="coerce").to_numpy()

    return DSCData(
        metadata=metadata,
        method_steps=method_steps,
        data=df,
        **extracted_arrays
    )