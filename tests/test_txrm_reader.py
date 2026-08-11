import pytest
import struct
from unittest.mock import patch, MagicMock
from readers_ientrance.txrm_reader import read_txrm, TxrmData

def test_read_txrm_file_not_found():
    """Test that the reader handles missing files gracefully."""
    result = read_txrm("non_existent_file.txrm")
    assert isinstance(result, TxrmData)
    assert "extraction_error" in result.metadata
    assert "File not found" in result.metadata["extraction_error"]

@patch("readers_ientrance.txrm_reader.os.path.exists")
@patch("readers_ientrance.txrm_reader.olefile")
def test_read_txrm_success(mock_olefile, mock_exists):
    """Test successful metadata parsing of a mocked 4.64 GB OLE2 TXRM file."""
    
    # 1. Setup Environment Mocks
    mock_exists.return_value = True
    mock_olefile.isOleFile.return_value = True

    # 2. Setup OLE File Mock
    mock_ole = MagicMock()
    mock_olefile.OleFileIO.return_value.__enter__.return_value = mock_ole

    # Mock the directory structure based on our terminal inspection
    mock_ole.listdir.return_value = [
        ["Version"],  # Root metadata
        ["ImageInfo", "AcquisitionMode"],
        ["AcquisitionSettings", "SrcVoltage"],
        ["TemperatureInfo", "Sensor1"],
        # Mocking the presence of image arrays without loading them
        ["ImageData1", "Image0"],
        ["ImageData1", "Image1"],
        ["ImageData1", "Image2"],
        ["ImageData2", "Image0"]
    ]

    # 3. Setup Binary Stream Decoding Mock
    def mock_openstream(path):
        """Simulates opening a stream and reading binary metadata."""
        stream_context = MagicMock()
        stream_file = MagicMock()
        
        if path == ["Version"]:
            # Null-terminated UTF-8 string
            stream_file.read.return_value = b'16.0\x00'
        elif path == ["ImageInfo", "AcquisitionMode"]:
            # 4-byte Int32 (Value: 1)
            stream_file.read.return_value = struct.pack('<i', 1)
        elif path == ["AcquisitionSettings", "SrcVoltage"]:
            # 4-byte Float32 (Value: 70.0)
            stream_file.read.return_value = struct.pack('<f', 70.0)
        else:
            stream_file.read.return_value = b'dummy_data'
            
        stream_context.__enter__.return_value = stream_file
        return stream_context

    mock_ole.openstream.side_effect = mock_openstream

    # 4. Execute the Reader
    result = read_txrm("dummy_path.txrm")

    # 5. Assertions: Root Metadata
    assert isinstance(result, TxrmData)
    assert result.metadata.get("Version") == "16.0"
    
    # 6. Assertions: Extracted Metadata Directories
    assert "AcquisitionMode" in result.image_info
    assert result.image_info["AcquisitionMode"]["int32"] == 1
    
    assert "SrcVoltage" in result.acquisition_settings
    assert result.acquisition_settings["SrcVoltage"]["float32"] == 70.0

    # 7. Assertions: Lazy Image Cataloging (Verify counts instead of arrays)
    assert result.metadata["Total_ImageData_Folders"] == 2
    # 3 images in ImageData1 + 1 image in ImageData2 = 4 total projections
    assert result.metadata["Total_Projections"] == 4 
    assert result.image_data_summary["ImageData1"] == 3
    assert result.image_data_summary["ImageData2"] == 1