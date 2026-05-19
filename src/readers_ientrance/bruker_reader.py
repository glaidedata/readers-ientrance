import numpy as np
import re
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional

# --- PYDANTIC MODELS ---

class ChannelData(BaseModel):
    """Holds the 2D array and all physics metadata for a specific Bruker scan."""
    data: np.ndarray
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

class BrukerAFMData(BaseModel):
    """Main model for the entire Bruker .003 file."""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    channels: Optional[Dict[str, ChannelData]] = Field(default_factory=dict)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


# --- MAIN READER ---

def read_bruker(file_path: str) -> BrukerAFMData:
    """Reads Bruker/Nanoscope AFM files (Images and Force Curves)."""
    
    metadata = {
        "File Format": "Bruker/Nanoscope",
        "Parser": "ASCII Header / Binary Offset"
    }
    channels = {}
    
    image_blocks = []
    current_block = {}

    # List of block names that contain actual binary offsets
    target_blocks = ["Ciao image list", "Ciao force image list"]
    
    # 1. Parse the ASCII Header
    with open(file_path, 'rb') as f:
        for line_bytes in f:
            try:
                line = line_bytes.decode('latin-1').strip()
            except UnicodeDecodeError:
                continue
            
            # Escape condition: End of the entire header
            if line.startswith(r"\*File list end"):
                if current_block.get("block_name") in target_blocks:
                    image_blocks.append(current_block)
                break
            
            # Detect a new section block
            if line.startswith(r"\*"):
                if current_block.get("block_name") in target_blocks:
                    image_blocks.append(current_block)
                
                block_name = line[2:].strip()
                current_block = {"block_name": block_name}
                continue
            
            # Parse Key-Value parameters inside the blocks
            if line.startswith("\\") and current_block:
                line_content = line[1:] # Strip the leading \
                
                # Handle Bruker's special '@' lines (e.g., @2:Image Data: S [Height] "Height")
                if line_content.startswith('@'):
                    content = line_content[1:]
                    match = re.match(r'(?:[0-9]+:)?(.*?):(.*)', content)
                    if match:
                        key = match.group(1).strip()
                        val = match.group(2).strip()
                    else:
                        continue
                # Handle standard lines (e.g., Data offset: 40960)
                elif ":" in line_content:
                    parts = line_content.split(":", 1)
                    key = parts[0].strip()
                    val = parts[1].strip()
                else:
                    continue
                
                # Store it in the local block (useful for image-specific metadata)
                current_block[key] = val
                
                # --- Specific Image Extraction Logic ---
                if current_block.get("block_name") in target_blocks:
                    if key == "Data offset":
                        current_block['offset'] = int(val)
                    elif key == "Data length":
                        current_block['length'] = int(val)
                    elif key == "Bytes/pixel":
                        current_block['bytes_per_pixel'] = int(val)
                    elif key == "Samps/line":
                        current_block['x_res'] = int(val.split()[0])
                    elif key == "Number of lines":
                        current_block['y_res'] = int(val)
                    elif key == "Line Direction" or key == "Z direction":
                        current_block['direction'] = val
                    elif "Image Data" in key: 
                        match = re.search(r'\"(.*?)\"', val)
                        if match:
                            current_block['channel_name'] = match.group(1)
                
                # --- Global Metadata Extraction ---
                else:
                    # This dumps EVERY single key from the header into our dictionary
                    # so the schema's 'raw_metadata' catch-all and specific lookups work perfectly.
                    metadata[key] = val
                    
                    # We keep these specific aliases so the base AFM properties 
                    # (like instrument_model and probe_id) continue to map cleanly.
                    if key == "Microscope":
                        metadata['instrument_model'] = val
                    elif key == "Tip Serial Number":
                        metadata['probe_id'] = val
                    elif key == "Scan Rate":
                        try:
                            metadata['scan_rate'] = float(val)
                        except ValueError:
                            pass
                    elif key == "Tip Radius":
                        try:
                            metadata['tip_radius'] = float(val)
                        except ValueError:
                            pass
                    elif key == "Scan Size":
                        try:
                            metadata['scan_size'] = float(val.split()[0]) 
                            metadata['scan_size_unit'] = val.split()[1] if len(val.split()) > 1 else ""
                        except ValueError:
                            pass
                    elif key == "Operating mode":
                        metadata['operating_mode'] = val

    # 2. Extract the Binary Matrices
    with open(file_path, 'rb') as f:
        for block in image_blocks:
            # Force curves do not have a y_res, so we only check for x_res
            if 'offset' in block and 'x_res' in block:
                offset = block['offset']
                x_res = block['x_res']
                # Default to 1 if y_res is missing (1D force curve)
                y_res = block.get('y_res', 1)
                bpp = block.get('bytes_per_pixel', 2)
                
                f.seek(offset)
                
                dtype = np.int16 if bpp == 2 else np.int32
                raw_data = np.fromfile(f, dtype=dtype, count=x_res * y_res)
                
                if len(raw_data) == x_res * y_res:
                    # .squeeze() automatically turns a (1, 4096) array into a flat 1D (4096,) array,
                    # while leaving 2D (512, 512) arrays perfectly intact!
                    image_array = raw_data.reshape((y_res, x_res)).squeeze()
                    
                    base_name = block.get('channel_name', f"Channel_{offset}")
                    direction = block.get('direction', '')
                    channel_name = f"{direction}_{base_name}" if direction else base_name
                    
                    channels[channel_name] = ChannelData(
                        data=image_array,
                        metadata=block
                    )

    return BrukerAFMData(
        metadata=metadata,
        channels=channels
    )