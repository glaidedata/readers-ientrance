import os
import numpy as np
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

try:
    import olefile
except ImportError:
    olefile = None

# Import our robust decoders from the RCP reader
from .rcp_reader import _decode_ole_stream, _extract_all_streams


# --- PYDANTIC MODELS ---

class TxrmData(BaseModel):
    """Main model for the ZEISS .txrm raw acquisition file."""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Core Metadata Directories
    image_info: Dict[str, Any] = Field(default_factory=dict)
    acquisition_settings: Dict[str, Any] = Field(default_factory=dict)
    recon_settings: Dict[str, Any] = Field(default_factory=dict)
    hw_stability: Dict[str, Any] = Field(default_factory=dict)
    temperature_info: Dict[str, Any] = Field(default_factory=dict)
    
    # Image catalog (Counts and paths, not raw bytes)
    image_data_summary: Dict[str, int] = Field(default_factory=dict)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

# --- HELPER FUNCTIONS ---

def extract_preview_image(file_path: str, target_stream: str = 'ImageData1/Image1', width: int = 1010, height: int = 1010) -> Optional[np.ndarray]:
    """
    Extracts a single 2D projection image from a ZEISS .txrm file.
    By default, grabs the very first image for preview purposes.
    Returns a 2D numpy array of the image, or None if extraction fails.
    """
    if olefile is None:
        print("ImportError: olefile required for image extraction.")
        return None

    if not olefile.isOleFile(file_path):
        return None

    try:
        with olefile.OleFileIO(file_path) as ole:
            # Check if the specific image stream exists
            stream_path = target_stream.split('/')
            if not ole.exists(stream_path):
                print(f"Stream {target_stream} not found.")
                return None

            with ole.openstream(stream_path) as stream:
                # Read the entire raw byte stream
                raw_bytes = stream.read()
                
            # Convert raw bytes to a 1D uint16 numpy array
            # Assuming DataType 5 (uint16) which is standard for TXRM projections
            image_1d = np.frombuffer(raw_bytes, dtype=np.uint16)
            
            # Reshape into the 2D grid based on the provided width and height
            try:
                image_2d = image_1d.reshape((height, width))
                return image_2d
            except ValueError as ve:
                print(f"Reshape Error: The stream size ({len(image_1d)} pixels) doesn't match {width}x{height}.")
                return None

    except Exception as e:
        print(f"Error during preview image extraction: {e}")
        return None



# --- MAIN READER ---

def read_txrm(file_path: str) -> TxrmData:
    """Reads metadata from a ZEISS .txrm file without loading heavy image arrays."""
    if olefile is None:
        raise ImportError("The 'olefile' package is required. Install it using 'pip install olefile'")

    metadata = {
        "File Format": "ZEISS TXRM (OLE2)",
        "Parser": "olefile (Metadata Only)"
    }
    
    if not os.path.exists(file_path):
        metadata["extraction_error"] = f"File not found: {file_path}"
        return TxrmData(metadata=metadata)

    if not olefile.isOleFile(file_path):
        metadata["extraction_error"] = f"Not a valid OLE2 file: {file_path}"
        return TxrmData(metadata=metadata)

    txrm_model = TxrmData(metadata=metadata)

    try:
        with olefile.OleFileIO(file_path) as ole:
            # 1. Extract Global Root Metadata (streams at the root level)
            root_streams = [entry[0] for entry in ole.listdir() if len(entry) == 1]
            for stream_name in root_streams:
                try:
                    with ole.openstream([stream_name]) as stream:
                        txrm_model.metadata[stream_name] = _decode_ole_stream(stream.read())
                except Exception as e:
                    txrm_model.metadata[stream_name] = f"Error: {e}"

            # 2. Extract High-Value Metadata Directories
            txrm_model.image_info = _extract_all_streams(ole, ["ImageInfo"])
            txrm_model.acquisition_settings = _extract_all_streams(ole, ["AcquisitionSettings"])
            txrm_model.recon_settings = _extract_all_streams(ole, ["ReconSettings"])
            txrm_model.hw_stability = _extract_all_streams(ole, ["HWStability"])
            txrm_model.temperature_info = _extract_all_streams(ole, ["TemperatureInfo"])

            # 3. Catalog the Image Data (Skip reading the binary arrays)
            # Find all root folders that start with "ImageData"
            all_entries = ole.listdir()
            image_folders = set(entry[0] for entry in all_entries if entry[0].startswith("ImageData"))
            
            for folder in image_folders:
                # Count how many projections/streams are in this specific ImageData folder
                item_count = sum(1 for entry in all_entries if entry[0] == folder)
                txrm_model.image_data_summary[folder] = item_count
                
            txrm_model.metadata["Total_ImageData_Folders"] = len(image_folders)
            txrm_model.metadata["Total_Projections"] = sum(txrm_model.image_data_summary.values())

    except Exception as e:
        txrm_model.metadata["extraction_error"] = str(e)

    return txrm_model