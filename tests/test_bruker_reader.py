import pytest
import numpy as np
from pathlib import Path
from readers_ientrance import read_bruker, BrukerAFMData

@pytest.fixture
def dummy_bruker_file(tmp_path: Path) -> str:
    """
    Creates a tiny, valid fake Bruker .003 file dynamically.
    This prevents us from having to commit a 40MB binary file to GitHub.
    """
    file_path = tmp_path / "fake_scan.003"
    
    # 1. Create a fake ASCII header perfectly mimicking a Bruker file
    header_text = (
        r"\*File list" + "\n"
        r"\Microscope: MultiMode 8" + "\n"
        r"\Scanner file: 9575jvlr.scn" + "\n"      # <-- Added to test Catch-All
        r"\Operating mode: PeakForce QNM" + "\n"   # <-- Added to test Catch-All
        r"\Scan Size: 10000 nm" + "\n"
        r"\Tip Radius: 15.5" + "\n"
        r"\*Ciao image list" + "\n"
        r"\Data offset: 500" + "\n"  
        r"\Data length: 8" + "\n"    
        r"\Bytes/pixel: 2" + "\n"
        r"\Samps/line: 2" + "\n"     
        r"\Number of lines: 2" + "\n"
        r"\Line Direction: Retrace" + "\n"
        r'\@2:Image Data: S [Height] "Height"' + "\n"
        r"\*File list end" + "\n"
    ).encode('latin-1')

    # 2. Add empty padding bytes until we reach exactly byte 500
    padding = b'\x00' * (500 - len(header_text))

    # 3. Create a fake 2x2 binary matrix (Values: 10, 20, 30, 40)
    fake_matrix = np.array([10, 20, 30, 40], dtype=np.int16)
    binary_data = fake_matrix.tobytes()

    # 4. Write it all to the temporary file
    with open(file_path, 'wb') as f:
        f.write(header_text)
        f.write(padding)
        f.write(binary_data)

    return str(file_path)


def test_bruker_reader_global_metadata(dummy_bruker_file):
    """Tests if the reader correctly extracts global metadata from the ASCII header."""
    
    # Run the reader!
    afm_data = read_bruker(dummy_bruker_file)
    
    # Assert it returns the correct Pydantic model
    assert isinstance(afm_data, BrukerAFMData)
    
    # Assert global metadata aliases worked
    assert afm_data.metadata.get("instrument_model") == "MultiMode 8"
    assert afm_data.metadata.get("scan_size") == 10000.0
    assert afm_data.metadata.get("tip_radius") == 15.5
    assert afm_data.metadata.get("File Format") == "Bruker/Nanoscope"

    # Assert the new 1000-line Catch-All logic worked!
    assert afm_data.metadata.get("Scanner file") == "9575jvlr.scn"
    assert afm_data.metadata.get("Operating mode") == "PeakForce QNM"


def test_bruker_reader_channel_extraction(dummy_bruker_file):
    """Tests if the reader correctly jumps to the offset and slices out the 2D array."""
    
    afm_data = read_bruker(dummy_bruker_file)
    
    # The dictionary key should be a combo of Direction + Name
    channel_name = "Retrace_Height"
    assert channel_name in afm_data.channels
    
    channel = afm_data.channels[channel_name]
    
    # Check channel metadata
    assert channel.metadata.get("offset") == 500 
    assert channel.metadata.get("x_res") == 2
    assert channel.metadata.get("y_res") == 2
    
    # Check the actual binary data! It should be a 2x2 array of int16
    assert channel.data.shape == (2, 2)
    assert channel.data.dtype == np.int16
    
    # Verify the exact pixel values match our fake matrix
    expected_matrix = np.array([[10, 20], [30, 40]], dtype=np.int16)
    np.testing.assert_array_equal(channel.data, expected_matrix)

def test_bruker_invalid_file(tmp_path):
    """Ensure the reader doesn't crash on an empty or invalid text file."""
    empty_file = tmp_path / "empty.003"
    empty_file.write_text("This is just some random text without Bruker headers.")
    
    afm_data = read_bruker(str(empty_file))
    
    assert isinstance(afm_data, BrukerAFMData)
    assert afm_data.channels == {}