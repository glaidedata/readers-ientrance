import os
import re
from typing import Dict, Any, Optional
import numpy as np
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

    # TXM specific dimension parameters
    recon_input_tomo_params: Dict[str, Any] = Field(default_factory=dict)
    
    # Image catalog (Counts and paths, not raw 3D voxel arrays)
    image_data_summary: Dict[str, int] = Field(default_factory=dict)
    total_planes: Optional[int] = None

    # Optional representative slice extracted without loading the full volume
    preview_image: Optional[np.ndarray] = Field(default=None, exclude=True)
    preview_slice_index: Optional[int] = None
    preview_stream_path: Optional[list[str]] = None
    preview_plane_index: Optional[int] = None
    preview_error: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


# --- PREVIEW HELPERS ---

def _natural_name_key(name: str):
    """Return a case-insensitive, numeric-aware key for an OLE entry name."""
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r'(\d+)', name)
        if part
    )


def _stream_path_key(path: list[str]):
    """Order a complete OLE stream path without assuming a fixed naming scheme."""
    return tuple(_natural_name_key(part) for part in path)


def _image_stream_paths(all_entries: list[list[str]]) -> list[list[str]]:
    """Discover reconstructed image streams and preserve their complete paths."""
    return sorted(
        [
            entry
            for entry in all_entries
            if len(entry) > 1 and entry[0].casefold().startswith('imagedata')
        ],
        key=_stream_path_key,
    )


def _positive_int(metadata: Dict[str, Any], key: str) -> Optional[int]:
    """Extract a positive integer from dual-decoded reader metadata."""
    value = metadata.get(key)
    if isinstance(value, dict):
        value = value.get('int32')
    if isinstance(value, (int, np.integer)) and value > 0:
        return int(value)
    return None


def _discover_verified_plane_layout(
    ole: 'olefile.OleFileIO',
    txm_model: TxmData,
    image_stream_paths: list[list[str]],
) -> tuple[Optional[list[tuple[list[str], int]]], Optional[str]]:
    """Return a complete verified mapping of image streams to plane counts."""
    width = _positive_int(txm_model.image_info, 'ImageWidth')
    height = _positive_int(txm_model.image_info, 'ImageHeight')
    if width is None or height is None:
        return None, 'Missing valid ImageWidth or ImageHeight metadata.'

    bytes_per_plane = width * height * np.dtype(np.uint16).itemsize
    stream_planes = []
    for path in image_stream_paths:
        try:
            stream_size = ole.get_size(path)
        except Exception:
            return None, 'No ImageData stream contains complete uint16 image planes.'

        if stream_size <= 0 or stream_size % bytes_per_plane != 0:
            return None, 'No ImageData stream contains complete uint16 image planes.'

        stream_planes.append((path, stream_size // bytes_per_plane))

    total_planes = sum(plane_count for _, plane_count in stream_planes)
    if total_planes == 0:
        return None, 'No ImageData stream contains complete uint16 image planes.'

    txm_model.total_planes = total_planes
    return stream_planes, None


def _extract_middle_slice(
    ole: 'olefile.OleFileIO',
    txm_model: TxmData,
    stream_planes: Optional[list[tuple[list[str], int]]],
    layout_error: Optional[str],
) -> None:
    """Decode the middle reconstructed plane from discovered TXM image streams."""
    total_planes = txm_model.total_planes
    if stream_planes is None or total_planes is None:
        txm_model.preview_error = layout_error
        return

    width = _positive_int(txm_model.image_info, 'ImageWidth')
    height = _positive_int(txm_model.image_info, 'ImageHeight')
    if width is None or height is None:
        txm_model.preview_error = 'Missing valid ImageWidth or ImageHeight metadata.'
        return

    middle_index = total_planes // 2
    preceding_planes = 0
    selected_path = None
    selected_plane_index = None
    selected_plane_count = None
    for path, plane_count in stream_planes:
        if middle_index < preceding_planes + plane_count:
            selected_path = path
            selected_plane_index = middle_index - preceding_planes
            selected_plane_count = plane_count
            break
        preceding_planes += plane_count

    if (
        selected_path is None
        or selected_plane_index is None
        or selected_plane_count is None
    ):
        txm_model.preview_error = 'Could not select the middle reconstructed plane.'
        return

    try:
        with ole.openstream(selected_path) as stream:
            raw_bytes = stream.read()
        image_data = np.frombuffer(raw_bytes, dtype=np.uint16)
        image_stack = image_data.reshape((selected_plane_count, height, width))
        txm_model.preview_image = image_stack[selected_plane_index].copy()
        txm_model.preview_slice_index = middle_index
        txm_model.preview_stream_path = list(selected_path)
        txm_model.preview_plane_index = selected_plane_index
    except Exception as e:
        txm_model.preview_error = f'Could not decode middle TXM slice: {e}'


# --- MAIN READER ---

def read_txm(file_path: str, *, include_preview: bool = False) -> TxmData:
    """Read TXM metadata and optionally decode one representative middle slice."""
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
            # Extract Global Root Metadata (streams at the root level)
            root_streams = [entry[0] for entry in ole.listdir() if len(entry) == 1]
            for stream_name in root_streams:
                try:
                    with ole.openstream([stream_name]) as stream:
                        txm_model.metadata[stream_name] = _decode_ole_stream(stream.read())
                except Exception as e:
                    txm_model.metadata[stream_name] = f"Error: {e}"

            # Extract High-Value Metadata Directories
            # TXM files usually contain extensive ReconSettings from the FDK algorithm
            txm_model.image_info = _extract_all_streams(ole, ["ImageInfo"])
            txm_model.acquisition_settings = _extract_all_streams(ole, ["AcquisitionSettings"])
            txm_model.recon_settings = _extract_all_streams(ole, ["ReconSettings"])

            # Extract the parameters containing the cropped dimensions
            txm_model.recon_input_tomo_params = _extract_all_streams(ole, ["ReconInputTomoParams"])

            # Catalog the 3D Image Data (Skip reading the binary arrays)
            # Find all root folders that start with "ImageData" to catalog slices/blocks
            all_entries = ole.listdir()
            image_stream_paths = _image_stream_paths(all_entries)
            image_folders = set(entry[0] for entry in all_entries if entry[0].startswith("ImageData"))
            
            for folder in image_folders:
                # Count how many slices/streams are in this specific ImageData folder
                item_count = sum(1 for entry in all_entries if entry[0] == folder)
                txm_model.image_data_summary[folder] = item_count
                
            txm_model.metadata["Total_ImageData_Folders"] = len(image_folders)
            txm_model.metadata["Total_3D_Slices_or_Blocks"] = sum(txm_model.image_data_summary.values())

            stream_planes, layout_error = _discover_verified_plane_layout(
                ole, txm_model, image_stream_paths
            )

            if include_preview:
                _extract_middle_slice(
                    ole, txm_model, stream_planes, layout_error
                )

    except Exception as e:
        txm_model.metadata["extraction_error"] = str(e)

    return txm_model
