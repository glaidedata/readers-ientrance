import pandas as pd
import numpy as np
import io
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional, List

class TADSCData(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    method_steps: List[str] = Field(default_factory=list)
    data: Optional[pd.DataFrame] = None

    # Generic DSC arrays
    time: Optional[np.ndarray] = None
    sample_temperature: Optional[np.ndarray] = None
    heat_flow: Optional[np.ndarray] = None
    heat_capacity: Optional[np.ndarray] = None
    approx_gas_flow: Optional[np.ndarray] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

def read_ta_dsc(filepath: str) -> TADSCData:
    """Reads a TA Instruments DSC .txt export file, automatically handling UTF-16/UTF-8 encoding."""
    metadata = {}
    method_steps = []
    data_lines = []
    signals = {}
    in_data_section = False

    # 1. Read as raw binary bytes first to prevent encoding crashes
    with open(filepath, "rb") as f:
        raw_bytes = f.read()

    # 2. Detect and decode UTF-16 encoding commonly used by TA Instruments on Windows
    text = raw_bytes.decode("utf-8", errors="ignore")
    if "\x00" in text:
        text = raw_bytes.decode("utf-16", errors="ignore")

    # 3. Process the decoded text line by line
    for line in text.splitlines():
        original_line = line
        line = line.strip()

        if not line:
            continue

        # Data block delimiter
        if line == "StartOfData":
            in_data_section = True
            continue

        if in_data_section:
            # Replace commas with dots for safety across regional locales
            data_lines.append(line.replace(',', '.'))
            continue

        # Parse Metadata Block
        parts = original_line.split('\t', 1)
        if len(parts) < 2:
            parts = original_line.split(' ', 1)

        if len(parts) == 2:
            key = parts[0].strip()
            val = parts[1].strip()

            if key.startswith('OrgMethod'):
                method_steps.append(val)
            elif key.startswith('Sig'):
                signals[key] = val
            elif key in metadata:
                metadata[key] = metadata[key] + " | " + val
            else:
                metadata[key] = val
        else:
            metadata[line] = ""

    # 4. Convert numeric blocks into structured data arrays
    df = pd.DataFrame()
    time_arr = temp_arr = hf_arr = hc_arr = gas_arr = None

    if data_lines:
        try:
            df = pd.read_csv(io.StringIO("\n".join(data_lines)), sep=r"\s+", header=None)
        except Exception:
            pass

        # Apply the Sig headers dynamically based on metadata keys
        col_names = []
        for i in range(1, len(df.columns) + 1):
            sig_key = f"Sig{i}"
            col_names.append(signals.get(sig_key, f"Column_{i}"))
        if len(col_names) == len(df.columns):
            df.columns = col_names

        # Map named columns to numeric arrays
        for col in df.columns:
            col_lower = col.lower()
            if "time" in col_lower:
                time_arr = pd.to_numeric(df[col], errors="coerce").to_numpy()
            elif "temperature" in col_lower:
                temp_arr = pd.to_numeric(df[col], errors="coerce").to_numpy()
            elif "heat flow" in col_lower:
                hf_arr = pd.to_numeric(df[col], errors="coerce").to_numpy()
            elif "capacity" in col_lower:
                hc_arr = pd.to_numeric(df[col], errors="coerce").to_numpy()
            elif "purge flow" in col_lower or "gas" in col_lower:
                gas_arr = pd.to_numeric(df[col], errors="coerce").to_numpy()

    return TADSCData(
        metadata=metadata,
        method_steps=method_steps,
        data=df,
        time=time_arr,
        sample_temperature=temp_arr,
        heat_flow=hf_arr,
        heat_capacity=hc_arr,
        approx_gas_flow=gas_arr
    )