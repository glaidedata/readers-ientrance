import os
from typing import Dict, Any
from pydantic import BaseModel, Field, ConfigDict

try:
    import olefile
except ImportError:
    olefile = None

# Import our robust decoders from the RCP reader
from .rcp_reader import _decode_ole_stream, _extract_all_streams


# --- PYDANTIC MODELS ---

class TxmData(BaseModel):
    """Main model for the ZEISS .txm 3D reconstructed volume file."""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Core Metadata Directories
    image_info: Dict[str, Any] = Field(default_factory=dict)
    acquisition_settings: Dict[str, Any] = Field(default_factory=dict)
    recon_settings: Dict[str, Any] = Field(default_factory=dict)
    
    # Image catalog (Counts and paths, not raw 3D voxel arrays)
    image_data_summary: Dict[str, int] = Field(default_factory=dict)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


# --- MAIN READER ---

def read_txm(file_path: str) -> TxmData:
    """Reads metadata from a ZEISS .txm file without loading heavy 3D voxel arrays."""
    if olefile is None:
        raise ImportError("The 'olefile' package is required. Install it using 'pip install olefile'")

    metadata = {
        "File Format": "ZEISS TXM (OLE2 3D Volume)",
        "Parser": "olefile (Metadata Only)"
    }
    
    if not os.path.exists(file_path):
        metadata["extraction_error"] = f"File not found: {file_path}"
        return TxmData(metadata=metadata)

    if not olefile.isOleFile(file_path):
        metadata["extraction_error"] = f"Not a valid OLE2 file: {file_path}"
        return TxmData(metadata=metadata)

    txm_model = TxmData(metadata=metadata)

    try:
        with olefile.OleFileIO(file_path) as ole:
            # 1. Extract Global Root Metadata (streams at the root level)
            root_streams = [entry[0] for entry in ole.listdir() if len(entry) == 1]
            for stream_name in root_streams:
                try:
                    with ole.openstream([stream_name]) as stream:
                        txm_model.metadata[stream_name] = _decode_ole_stream(stream.read())
                except Exception as e:
                    txm_model.metadata[stream_name] = f"Error: {e}"

            # 2. Extract High-Value Metadata Directories
            # TXM files usually contain extensive ReconSettings from the FDK algorithm
            txm_model.image_info = _extract_all_streams(ole, ["ImageInfo"])
            txm_model.acquisition_settings = _extract_all_streams(ole, ["AcquisitionSettings"])
            txm_model.recon_settings = _extract_all_streams(ole, ["ReconSettings"])

            # 3. Catalog the 3D Image Data (Skip reading the binary arrays)
            # Find all root folders that start with "ImageData" to catalog slices/blocks
            all_entries = ole.listdir()
            image_folders = set(entry[0] for entry in all_entries if entry[0].startswith("ImageData"))
            
            for folder in image_folders:
                # Count how many slices/streams are in this specific ImageData folder
                item_count = sum(1 for entry in all_entries if entry[0] == folder)
                txm_model.image_data_summary[folder] = item_count
                
            txm_model.metadata["Total_ImageData_Folders"] = len(image_folders)
            txm_model.metadata["Total_3D_Slices_or_Blocks"] = sum(txm_model.image_data_summary.values())

    except Exception as e:
        txm_model.metadata["extraction_error"] = str(e)

    return txm_model