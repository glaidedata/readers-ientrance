import pandas as pd
import re
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional, List

class ALDData(BaseModel):
    system_name: str = ""
    start_timestamp: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    port_configurations: Dict[str, str] = Field(default_factory=dict)
    precursor_doses: Dict[str, str] = Field(default_factory=dict)
    running_rcp: List[List[str]] = Field(default_factory=list)
    communication_data: Optional[pd.DataFrame] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

def read_italya_ald(filepath: str) -> ALDData:
    system_name = ""
    start_timestamp = ""
    metadata = {}
    port_configurations = {}
    precursor_doses = {}
    running_rcp = []
    communication_records = []

    current_section = None

    # Regex to catch the section headers
    section_header_pattern = re.compile(r'-{10,}(.+?)-{10,}')

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        original_line = line
        line = line.strip()

        if not line:
            continue

        # Extract the initial timestamp at the very top of the file
        if current_section is None and i == 0 and not line.startswith("-"):
            start_timestamp = line
            continue

        # Check for section headers
        match = section_header_pattern.search(line)
        if match:
            current_section = match.group(1).strip()
            continue

        # --- Parse based on the current section ---
        if current_section == "System Name":
            system_name = line

        elif current_section == "System Configurations":
            if "&" in line:
                key, val = line.split("&", 1)
                metadata[key.strip()] = val.strip()

        elif current_section == "Port Configurations":
            if ":" in line:
                key, val = line.split(":", 1)
                port_configurations[key.strip()] = val.strip()

        elif current_section == "Precursor Dose Time Until Now":
            # Data format: TMA\t11760milliseconds
            parts = original_line.split("\t")
            if len(parts) >= 2:
                precursor_doses[parts[0].strip()] = parts[1].strip()

        elif current_section == "Running RCP":
            # Tab separated recipe steps
            parts = [p.strip() for p in original_line.split("\t") if p.strip()]
            if parts:
                running_rcp.append(parts)

        elif current_section == "Communication Data":
            # Data format: 10.02.2026 15:33:22\tPressure:\t1.76e+002
            parts = original_line.split("\t")
            if len(parts) >= 3:
                timestamp = parts[0].strip()
                sensor = parts[1].replace(":", "").strip()
                try:
                    value = float(parts[2].strip())
                except ValueError:
                    value = parts[2].strip()
                
                communication_records.append({
                    "timestamp": timestamp,
                    "sensor": sensor,
                    "value": value
                })

    # Convert the communication logs into a DataFrame
    df_comm = pd.DataFrame(communication_records) if communication_records else pd.DataFrame()

    return ALDData(
        system_name=system_name,
        start_timestamp=start_timestamp,
        metadata=metadata,
        port_configurations=port_configurations,
        precursor_doses=precursor_doses,
        running_rcp=running_rcp,
        communication_data=df_comm if not df_comm.empty else None
    )