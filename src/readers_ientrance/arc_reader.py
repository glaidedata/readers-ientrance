import io
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


class ARCData(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    data: Optional[pd.DataFrame] = None

    # Exact Arrays from the Semicolon Table
    serial_number: Optional[np.ndarray] = None
    current_time: Optional[np.ndarray] = None  # Stored as string array (HH:MM:SS)
    sample_temperature: Optional[np.ndarray] = None
    top_temperature: Optional[np.ndarray] = None
    wall_temperature: Optional[np.ndarray] = None
    bottom_temperature: Optional[np.ndarray] = None
    jacket_temperature: Optional[np.ndarray] = None
    pressure: Optional[np.ndarray] = None
    power1: Optional[np.ndarray] = None
    power2: Optional[np.ndarray] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


def read_arc(filepath: str) -> ARCData:
    """Reads a semicolon-separated ARC text file."""
    metadata = {}
    data_lines = []
    in_data_section = False

    with open(filepath, "rb") as f:
        raw_bytes = f.read()

    text = raw_bytes.decode("utf-8", errors="ignore")
    if "\x00" in text:
        text = raw_bytes.decode("utf-16", errors="ignore")

    for line in text.splitlines():
        original_line = line
        line = line.strip()

        if not line:
            continue

        # Detect the exact start of the semicolon data table
        if line.startswith("Serial Number;Current Time;Sample Temperature"):
            in_data_section = True
            data_lines.append(original_line)
            continue

        if in_data_section:
            data_lines.append(original_line.replace(',', '.'))
            continue

        # Extract Metadata by splitting at the first semicolon
        parts = original_line.split(';', 1)
        if len(parts) >= 2:
            key = parts[0].strip()
            val = parts[1].strip()
            metadata[key] = val

    df = pd.DataFrame()
    arrays = {
        "serial_number": None, "current_time": None, "sample_temperature": None,
        "top_temperature": None, "wall_temperature": None, "bottom_temperature": None,
        "jacket_temperature": None, "pressure": None, "power1": None, "power2": None
    }

    if data_lines:
        try:
            # Parse the table cleanly using the semicolon separator
            df = pd.read_csv(io.StringIO("\n".join(data_lines)), sep=';')
            df.columns = df.columns.str.strip()

            if "Serial Number" in df.columns: arrays["serial_number"] = pd.to_numeric(df["Serial Number"], errors="coerce").to_numpy()
            if "Current Time" in df.columns: arrays["current_time"] = df["Current Time"].astype(str).to_numpy()
            if "Sample Temperature" in df.columns: arrays["sample_temperature"] = pd.to_numeric(df["Sample Temperature"], errors="coerce").to_numpy()
            if "Top Temperature" in df.columns: arrays["top_temperature"] = pd.to_numeric(df["Top Temperature"], errors="coerce").to_numpy()
            if "Wall Temperature" in df.columns: arrays["wall_temperature"] = pd.to_numeric(df["Wall Temperature"], errors="coerce").to_numpy()
            if "Bottom Temperature" in df.columns: arrays["bottom_temperature"] = pd.to_numeric(df["Bottom Temperature"], errors="coerce").to_numpy()
            if "Jacket Temperature" in df.columns: arrays["jacket_temperature"] = pd.to_numeric(df["Jacket Temperature"], errors="coerce").to_numpy()
            if "Pressure" in df.columns: arrays["pressure"] = pd.to_numeric(df["Pressure"], errors="coerce").to_numpy()
            if "Power1" in df.columns: arrays["power1"] = pd.to_numeric(df["Power1"], errors="coerce").to_numpy()
            if "Power2" in df.columns: arrays["power2"] = pd.to_numeric(df["Power2"], errors="coerce").to_numpy()
        except Exception:
            pass

    return ARCData(metadata=metadata, data=df, **arrays)