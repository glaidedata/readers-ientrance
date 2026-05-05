import numpy as np
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional
from pathlib import Path

from .nt_mdt import NtMdt 

def _extract_kaitai_meta(k_obj: Any) -> Dict[str, Any]:
    """
    Dynamically sweeps through a Kaitai Struct object and extracts all 
    public properties into a dictionary so nothing is missed.
    """
    meta = {}
    if not k_obj:
        return meta
        
    for attr in dir(k_obj):
        # Skip private/internal Kaitai attributes and methods
        if attr.startswith('_') or attr in ['from_file', 'from_bytes', 'from_io', 'close']:
            continue
            
        try:
            val = getattr(k_obj, attr)
            
            # Skip functions/methods
            if callable(val):
                continue
                
            # If the value is an Enum (like DataType or Unit), save its string name
            if hasattr(val, 'name'):
                meta[attr] = val.name
            # If the value is another nested Kaitai struct, extract it recursively
            elif hasattr(val, '_io'):
                meta[attr] = _extract_kaitai_meta(val)
            # Ignore massive raw data lists/bytes in the metadata dictionary
            elif isinstance(val, (list, bytes, bytearray)):
                continue
            else:
                meta[attr] = val
        except Exception:
            # Safely skip any attributes that fail to evaluate
            continue
            
    return meta


# --- PYDANTIC MODELS ---

class ChannelData(BaseModel):
    """Holds the 2D array and all physics metadata for a specific scan."""
    data: np.ndarray
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

class NTMDTAFMData(BaseModel):
    """Main model for the entire .mdt file."""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    channels: Optional[Dict[str, ChannelData]] = Field(default_factory=dict)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


# --- MAIN READER ---

def read_ntmdt(file_path: str) -> NTMDTAFMData:
    if Path(file_path).suffix.lower() != ".mdt":
        raise ValueError(f"File {file_path} is not an .mdt file.")

    # Parse the binary file using Kaitai Struct
    mdt_file = NtMdt.from_file(file_path)
    mdt_file._read()
    
    parsed_metadata = {
        "Measurement Type": "AFM",
        "File Format": "NT-MDT (.mdt)",
        "Parser": "Kaitai Struct",
        "Total Frames": mdt_file.last_frame + 1
    }
    parsed_channels = {}

    for i, frame in enumerate(mdt_file.frames.frames):
        main = frame.main
        frame_type_name = main.type.name 
        
        if frame_type_name == "scanned":
            scanned_data = main.frame_data
            
            x_res = scanned_data.fm_xres
            y_res = scanned_data.fm_yres
            
            # 1. Dynamically extract ALL physics variables (velocity, scales, etc.)
            channel_meta = {}
            if hasattr(scanned_data, 'vars'):
                channel_meta = _extract_kaitai_meta(scanned_data.vars)
                
            # Add the resolution
            channel_meta["x_resolution"] = x_res
            channel_meta["y_resolution"] = y_res
            
            # Extract any embedded XML if it exists
            if hasattr(scanned_data, 'xml') and hasattr(scanned_data.xml, 'xml'):
                 channel_meta["xml_metadata"] = scanned_data.xml.xml

            # 2. Extract the 2D Data Array
            raw_pixels = scanned_data.image
            if raw_pixels and len(raw_pixels) == x_res * y_res:
                image_array = np.array(raw_pixels).reshape((y_res, x_res))
                
                # Get the title (e.g., "1F:Phase1")
                channel_name = f"Channel_{i}_{frame_type_name}"
                if hasattr(scanned_data, 'title') and scanned_data.title.title:
                     channel_name = scanned_data.title.title

                # 3. Store in the Pydantic model (Array + Metadata)
                parsed_channels[channel_name] = ChannelData(
                    data=image_array,
                    metadata=channel_meta
                )

    return NTMDTAFMData(
        metadata=parsed_metadata,
        channels=parsed_channels
    )