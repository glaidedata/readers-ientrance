import os
import struct
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

try:
    import olefile
except ImportError:
    olefile = None


# --- PYDANTIC MODELS ---

class AcquisitionSettings(BaseModel):
    """Holds all acquisition parameters for a specific recipe point."""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(arbitrary_types_allowed=True)

class ReconSettings(BaseModel):
    """Holds all reconstruction parameters for a specific recipe point."""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
class RecipePoint(BaseModel):
    """Represents a single scan/warmup step within the RCP sequence."""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    acquisition_settings: AcquisitionSettings = Field(default_factory=AcquisitionSettings)
    recon_settings: ReconSettings = Field(default_factory=ReconSettings)
    model_config = ConfigDict(arbitrary_types_allowed=True)

class RcpData(BaseModel):
    """Main model for the entire ZEISS .rcp configuration file."""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    recipe_points: Dict[str, RecipePoint] = Field(default_factory=dict)
    model_config = ConfigDict(arbitrary_types_allowed=True)


# --- HELPER FUNCTIONS ---

def _decode_ole_stream(data: bytes) -> Any:
    """Decodes OLE binary streams by safely guessing String, Int, or Float types."""
    if not data:
        return None

    length = len(data)

    # 1. Attempt String Decoding (Windows OLE strings are null-terminated)
    # Try UTF-16-LE first (Standard for Windows OLE)
    try:
        # Decode first, THEN strip the null characters. 
        text = data.decode('utf-16-le').strip('\x00')
        # Basic heuristic to avoid false positive unicode decodes
        if text.isprintable() and len(text) > 0 and not any(ord(c) > 10000 for c in text): 
            return text
    except UnicodeDecodeError:
        pass

    # Try Standard UTF-8
    try:
        text = data.decode('utf-8').strip('\x00')
        if text.isprintable():
            return text
    except UnicodeDecodeError:
        pass

    # 2. Number Decoding: 4-Byte (Int32 or Float32)
    if length == 4:
        val_int = struct.unpack('<i', data)[0]
        val_float = struct.unpack('<f', data)[0]
        # Return both so the consuming plugin can pick the correct physical unit
        return {"int32": val_int, "float32": round(val_float, 6)}

    # 3. Number Decoding: 8-Byte (Int64 or Double64)
    if length == 8:
        val_int64 = struct.unpack('<q', data)[0]
        val_double = struct.unpack('<d', data)[0]
        return {"int64": val_int64, "double64": round(val_double, 6)}

    # 4. Fallback for raw binary objects
    return data.hex()

def _extract_all_streams(ole: 'olefile.OleFileIO', base_path: list) -> Dict[str, Any]:
    """Extracts streams under a given base path, flattening sub-directories."""
    result = {}
    for entry in ole.listdir():
        # Match entries that start with the target base path
        if len(entry) > len(base_path) and entry[:len(base_path)] == base_path:
            # Flatten deeper nested paths (e.g., CropRectangle -> Rectangle -> Bottom)
            key = "_".join(entry[len(base_path):])
            try:
                with ole.openstream(entry) as stream:
                    result[key] = _decode_ole_stream(stream.read())
            except Exception as e:
                result[key] = f"Error: {str(e)}"
    return result


# --- MAIN READER ---

def read_rcp(file_path: str) -> RcpData:
    """Reads a ZEISS .rcp Recipe file and returns a structured Pydantic model."""
    if olefile is None:
        raise ImportError("The 'olefile' package is required. Install it using 'pip install olefile'")

    metadata = {
        "File Format": "ZEISS RCP (OLE2)",
        "Parser": "olefile"
    }
    recipe_points = {}
    
    if not os.path.exists(file_path):
        metadata["extraction_error"] = f"File not found: {file_path}"
        return RcpData(metadata=metadata)

    if not olefile.isOleFile(file_path):
        metadata["extraction_error"] = f"Not a valid OLE2 file: {file_path}"
        return RcpData(metadata=metadata)

    try:
        with olefile.OleFileIO(file_path) as ole:
            # 1. Extract Global Root Metadata
            root_entries = [entry[0] for entry in ole.listdir() if len(entry) == 1]
            
            for entry_name in root_entries:
                if not entry_name.startswith("RecipePoint"):
                    try:
                        with ole.openstream([entry_name]) as stream:
                            metadata[entry_name] = _decode_ole_stream(stream.read())
                    except Exception as e:
                        metadata[entry_name] = f"Error: {e}"
                        
            # 2. Extract Individual Recipe Points (Warmups and Scans)
            point_names = sorted([name for name in root_entries if name.startswith("RecipePoint")])
            
            for p_name in point_names:
                rp = RecipePoint()
                
                # Top level metadata for the RecipePoint (e.g., PointName, MagStr)
                point_entries = [entry for entry in ole.listdir() if len(entry) == 2 and entry[0] == p_name]
                for entry in point_entries:
                    stream_name = entry[-1]
                    if stream_name not in ["AcquisitionSettings", "ReconSettings", "AutoStitchSettings"]:
                        try:
                            with ole.openstream(entry) as stream:
                                rp.metadata[stream_name] = _decode_ole_stream(stream.read())
                        except Exception:
                            pass
                
                # Extract structured settings sub-directories
                rp.acquisition_settings.metadata = _extract_all_streams(ole, [p_name, "AcquisitionSettings"])
                rp.recon_settings.metadata = _extract_all_streams(ole, [p_name, "ReconSettings"])
                
                # Catch AutoStitchSettings if available in metadata
                stitch_data = _extract_all_streams(ole, [p_name, "AutoStitchSettings"])
                if stitch_data:
                    rp.metadata["AutoStitchSettings"] = stitch_data
                
                recipe_points[p_name] = rp

    except Exception as e:
        metadata["extraction_error"] = str(e)

    return RcpData(
        metadata=metadata,
        recipe_points=recipe_points
    )