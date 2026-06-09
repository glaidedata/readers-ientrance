import numpy as np
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional

try:
    import spc_spectra as spc
except ImportError:
    spc = None

# --- PYDANTIC MODELS ---

class SPCData(BaseModel):
    """Main model for .spc (Spectroscopic Binary) files."""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Core spectral data
    x_data: Optional[np.ndarray] = None
    spectra: Optional[np.ndarray] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

# --- MAIN READER ---

def read_spc(file_path: str) -> SPCData:
    """
    Reads a standard .spc (Spectroscopic Binary) file.
    """
    if spc is None:
        raise ImportError("The 'spc' package is required. Install it using 'pip install spc'")

    f = spc.File(file_path)

    # Extracted x-axis array (typically wavenumber or wavelength)
    x_data = f.x

    # Extract spectra and any individual subfile metadata (e.g., Z-coordinates, timestamps)
    spectra = []
    subfile_metadata = []
    for sub in f.sub:
        spectra.append(sub.y)
        
        # Scrape metadata specific to this individual sub-scan
        sub_meta = {}
        for k in dir(sub):
            if not k.startswith('_') and k not in ['x', 'y'] and not callable(getattr(sub, k)):
                val = getattr(sub, k)
                if not isinstance(val, (np.ndarray, list, dict)):
                    if isinstance(val, bytes):
                        val = val.decode('utf-8', errors='ignore').strip('\x00')
                    sub_meta[k] = val
        if sub_meta:
            subfile_metadata.append(sub_meta)

    spectra = np.array(spectra)

    # If it's just a single point scan, flatten it to a 1D array
    if spectra.shape[0] == 1:
        spectra = spectra[0]

    # Initialize dynamic metadata with known keys
    metadata = {
        "File Format": "Galactic SPC",
        "Parser": "spc",
        "number_of_subfiles": len(f.sub),
        "spectral_points": len(x_data) if x_data is not None else 0
    }

    if subfile_metadata:
        metadata["subfile_metadata"] = subfile_metadata

    # Aggressively grab all attributes from the main file header
    for key in dir(f):
        if not key.startswith('_') and key not in ['x', 'y', 'sub']:
            try:
                val = getattr(f, key)
                # Filter out methods, arrays, and complex objects
                if not callable(val) and not isinstance(val, (np.ndarray, list, dict)):
                    # SPC files heavily use byte strings, decode them for JSON safety
                    if isinstance(val, bytes):
                        val = val.decode('utf-8', errors='ignore').strip('\x00')
                    
                    # Prevent overwriting manually set keys and ignore empty strings
                    if key not in metadata and val != "":
                        metadata[key] = val
            except Exception:
                pass

    return SPCData(
        metadata=metadata,
        x_data=x_data,
        spectra=spectra
    )