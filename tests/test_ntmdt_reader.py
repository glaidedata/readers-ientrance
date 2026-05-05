import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from readers_ientrance.ntmdt_reader import read_ntmdt, NTMDTAFMData

@patch("readers_ientrance.ntmdt_reader.NtMdt.from_file")
def test_read_ntmdt_success(mock_from_file, tmp_path):
    # 1. Setup mock Kaitai Struct data tree
    mock_mdt = MagicMock()
    mock_mdt.last_frame = 0  # Total frames = last_frame + 1 (so 1 frame)
    
    # Create a mock frame of type 'scanned'
    mock_frame = MagicMock()
    mock_frame.main.type.name = "scanned"
    
    # Fill it with dummy data representing a 2x2 image scan
    mock_frame_data = MagicMock()
    mock_frame_data.fm_xres = 2
    mock_frame_data.fm_yres = 2
    mock_frame_data.title.title = "Height Sensor"
    mock_frame_data.image = [10, 20, 30, 40]  # Kaitai outputs a flat 1D list
    
    mock_frame.main.frame_data = mock_frame_data
    mock_mdt.frames.frames = [mock_frame]

    # Attach the mock to the from_file call
    mock_from_file.return_value = mock_mdt

    # 2. Create a dummy file path to pass the extension check
    dummy_file = tmp_path / "test_scan.mdt"
    dummy_file.touch()

    # 3. Execute the reader
    result = read_ntmdt(str(dummy_file))

    # 4. Assertions to ensure Pydantic model and dynamic extraction worked
    assert isinstance(result, NTMDTAFMData)

    # Verify our code actually told Kaitai to read the bytes
    mock_mdt._read.assert_called_once()
    
    # Check metadata
    assert result.metadata["Total Frames"] == 1
    assert result.metadata["Parser"] == "Kaitai Struct"
    assert result.metadata["File Format"] == "NT-MDT (.mdt)"
    
    # Check data channels and reshaping logic
    assert "Height Sensor" in result.channels
    
    # A 1D list of [10, 20, 30, 40] with a 2x2 resolution should reshape like this:
    expected_array = np.array([[10, 20], [30, 40]])
    np.testing.assert_array_equal(result.channels["Height Sensor"], expected_array)


def test_read_ntmdt_invalid_extension(tmp_path):
    bad_file = tmp_path / "test_scan.txt"
    bad_file.touch()
    
    with pytest.raises(ValueError, match="is not an .mdt file"):
        read_ntmdt(str(bad_file))