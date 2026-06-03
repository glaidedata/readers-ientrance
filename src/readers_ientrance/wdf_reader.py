import numpy as np
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional
import io

try:
    from renishawWiRE import WDFReader
except ImportError:
    WDFReader = None

# --- PYDANTIC MODELS ---

class RenishawRamanData(BaseModel):
    """Main model for Renishaw .wdf Raman spectroscopy files."""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Core spectral data
    wavenumber: Optional[np.ndarray] = None
    spectra: Optional[np.ndarray] = None
    
    # Mapping/Spatial coordinates
    xpos: Optional[np.ndarray] = None
    ypos: Optional[np.ndarray] = None
    zpos: Optional[np.ndarray] = None
    
    # White-light image data
    white_light_image: Optional[bytes] = None
    image_metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

# --- MAIN READER ---

def read_renishaw_wdf(file_path: str) -> RenishawRamanData:
    """
    Reads Renishaw .wdf Raman files using the renishawWiRE library.
    Handles single point, depth series, and 2D mapping data.
    """
    if WDFReader is None:
        raise ImportError("The 'renishawWiRE' package is required. Install it using 'pip install renishawWiRE'")

    # Initialize the reader
    reader = WDFReader(file_path)
    
    # Extract core spectral data
    wavenumber = reader.xdata
    spectra = reader.spectra
    
    # Extract coordinates depending on measurement type
    xpos = getattr(reader, 'xpos', None)
    ypos = getattr(reader, 'ypos', None)
    zpos = getattr(reader, 'zpos', None)
    
    # Extract white-light image if it exists 
    img_bytes = None
    img_metadata = {}
    
    if hasattr(reader, 'img') and reader.img is not None:
        try:
            if isinstance(reader.img, io.BytesIO):
                img_bytes = reader.img.getvalue()
            
            if hasattr(reader, 'img_origins'):
                img_metadata['img_origins'] = reader.img_origins
            if hasattr(reader, 'img_dimensions'):
                img_metadata['img_dimensions'] = reader.img_dimensions
            if hasattr(reader, 'img_cropbox'):
                img_metadata['img_cropbox'] = reader.img_cropbox
        except Exception as e:
            img_metadata['extraction_error'] = str(e)

    # Extract dynamic metadata
    metadata = {
        "File Format": "Renishaw WDF",
        "Parser": "renishawWiRE",
        "measurement_type": getattr(reader, 'measurement_type', None),
        "laser_length": getattr(reader, 'laser_length', None),
        "title": getattr(reader, 'title', ""),
        "application": getattr(reader, 'application', ""),
        "accumulation_count": getattr(reader, 'accumulation_count', None),
        "measurement_time": getattr(reader, 'measurement_time', None),
        "spectral_points": len(wavenumber) if wavenumber is not None else 0
    }
    
    # Catch any other top-level simple attributes stored in the reader object
    for key, value in vars(reader).items():
        if not key.startswith('_') and not isinstance(value, (np.ndarray, list, dict, io.IOBase)):
            if key not in metadata:
                metadata[key] = value

    return RenishawRamanData(
        metadata=metadata,
        wavenumber=wavenumber,
        spectra=spectra,
        xpos=xpos,
        ypos=ypos,
        zpos=zpos,
        white_light_image=img_bytes,
        image_metadata=img_metadata
    )