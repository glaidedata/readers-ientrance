import pytest
import struct
from unittest.mock import patch, MagicMock
from readers_ientrance.rcp_reader import read_rcp, RcpData, RecipePoint

def test_read_rcp_file_not_found():
    """Test that the reader handles missing files gracefully."""
    result = read_rcp("non_existent_file.rcp")
    assert isinstance(result, RcpData)
    assert "extraction_error" in result.metadata
    assert "File not found" in result.metadata["extraction_error"]

@patch("readers_ientrance.rcp_reader.os.path.exists")
@patch("readers_ientrance.rcp_reader.olefile")
def test_read_rcp_success(mock_olefile, mock_exists):
    """Test successful parsing of a mocked OLE2 RCP file."""
    
    # 1. Setup Environment Mocks
    mock_exists.return_value = True
    mock_olefile.isOleFile.return_value = True

    # 2. Setup OLE File Mock
    mock_ole = MagicMock()
    # Mock the context manager behavior: `with olefile.OleFileIO(...) as ole:`
    mock_olefile.OleFileIO.return_value.__enter__.return_value = mock_ole

    # Mock the directory structure we discovered via inspection
    mock_ole.listdir.return_value = [
        ["RecipeName"],
        ["NoOfTomoDataSets"],
        ["RecipePoint0"],
        ["RecipePoint0", "PointName"],
        ["RecipePoint0", "AcquisitionSettings"],
        ["RecipePoint0", "AcquisitionSettings", "SrcVoltage"],
        ["RecipePoint0", "AcquisitionSettings", "ExpTime"],
        ["RecipePoint0", "ReconSettings"],
        ["RecipePoint0", "ReconSettings", "BeamHardening"]
    ]

    # 3. Setup Binary Stream Decoding Mock
    def mock_openstream(path):
        """Simulates opening a stream and reading binary data."""
        stream_context = MagicMock()
        stream_file = MagicMock()
        
        if path == ["RecipeName"]:
            # Null-terminated UTF-16 string
            stream_file.read.return_value = "LFP3_5c".encode('utf-16-le') + b'\x00\x00'
        elif path == ["NoOfTomoDataSets"]:
            # 4-byte Int32 (Value: 4)
            stream_file.read.return_value = struct.pack('<i', 4)
        elif path == ["RecipePoint0", "PointName"]:
            # Null-terminated UTF-8 string
            stream_file.read.return_value = b'warmupA\x00'
        elif path == ["RecipePoint0", "AcquisitionSettings", "SrcVoltage"]:
            # 4-byte Float32 (Value: 70.0)
            stream_file.read.return_value = struct.pack('<f', 70.0)
        elif path == ["RecipePoint0", "AcquisitionSettings", "ExpTime"]:
            # 4-byte Float32 (Value: 1.0)
            stream_file.read.return_value = struct.pack('<f', 1.0)
        else:
            stream_file.read.return_value = b'dummy_data'
            
        # Hook up the context manager to return our mock file
        stream_context.__enter__.return_value = stream_file
        return stream_context

    mock_ole.openstream.side_effect = mock_openstream

    # 4. Execute the Reader
    result = read_rcp("dummy_path.rcp")

    # 5. Assertions: Global Metadata
    assert isinstance(result, RcpData)
    assert result.metadata["RecipeName"] == "LFP3_5c"
    
    # Check that our numeric dual-decoding logic works
    assert "int32" in result.metadata["NoOfTomoDataSets"]
    assert result.metadata["NoOfTomoDataSets"]["int32"] == 4

    # 6. Assertions: Recipe Point Data
    assert "RecipePoint0" in result.recipe_points
    rp0 = result.recipe_points["RecipePoint0"]
    assert isinstance(rp0, RecipePoint)
    assert rp0.metadata["PointName"] == "warmupA"

    # 7. Assertions: Nested Settings Directories
    acq_settings = rp0.acquisition_settings.metadata
    assert "SrcVoltage" in acq_settings
    assert acq_settings["SrcVoltage"]["float32"] == 70.0
    assert acq_settings["ExpTime"]["float32"] == 1.0