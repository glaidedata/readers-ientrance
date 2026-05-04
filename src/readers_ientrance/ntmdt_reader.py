import numpy as np
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any
from pathlib import Path

# Import the Kaitai Struct parser you just added
from .nt_mdt import NtMdt 

class NTMDTAFMData(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    channels: Dict[str, np.ndarray] = Field(default_factory=dict)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

def read_ntmdt(file_path: str) -> NTMDTAFMData:
    """Reads NT-MDT (.mdt) binary files using the Kaitai Struct parser."""
    if Path(file_path).suffix.lower() != ".mdt":
        raise ValueError(f"File {file_path} is not an .mdt file.")

    # 1. Parse the binary file using Kaitai Struct
    mdt_file = NtMdt.from_file(file_path)

    mdt_file._read()
    
    parsed_metadata = {
        "Measurement Type": "AFM",
        "File Format": "NT-MDT (.mdt)",
        "Parser": "Kaitai Struct",
        "Total Frames": mdt_file.last_frame + 1
    }
    parsed_channels = {}

    # 2. Iterate through the frames to extract data
    for i, frame in enumerate(mdt_file.frames.frames):
        main = frame.main
        
        # Check what type of frame this is (scanned image, spectroscopy curve, etc.)
        frame_type_name = main.type.name 
        
        if frame_type_name == "scanned":
            scanned_data = main.frame_data
            
            # Extract resolution
            x_res = scanned_data.fm_xres
            y_res = scanned_data.fm_yres
            
            # Extract the raw 1D list of pixels and reshape it into a 2D numpy array
            raw_pixels = scanned_data.image
            if raw_pixels and len(raw_pixels) == x_res * y_res:
                image_array = np.array(raw_pixels).reshape((y_res, x_res))
                
                # Try to get the signal name (e.g., Height, Phase) from the XML or Title if available, 
                # otherwise default to a generic name.
                channel_name = f"Channel_{i}_{frame_type_name}"
                if hasattr(scanned_data, 'title') and scanned_data.title.title:
                     channel_name = scanned_data.title.title

                parsed_channels[channel_name] = image_array

    return NTMDTAFMData(
        metadata=parsed_metadata,
        channels=parsed_channels
    )