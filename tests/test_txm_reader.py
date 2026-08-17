import struct
from unittest.mock import MagicMock, patch

import pytest
from readers_ientrance.txm_reader import TxmData, read_txm


def test_read_txm_file_not_found():
    """Test that the reader gracefully handles non-existent files."""
    with patch('os.path.exists', return_value=False):
        result = read_txm('missing_volume.txm')
        
        assert isinstance(result, TxmData)
        assert 'extraction_error' in result.metadata
        assert 'File not found' in result.metadata['extraction_error']


def test_read_txm_invalid_ole_file():
    """Test that the reader flags invalid or corrupted OLE2 containers."""
    with patch('os.path.exists', return_value=True), \
         patch('olefile.isOleFile', return_value=False):
        
        result = read_txm('corrupted_volume.txm')
        
        assert isinstance(result, TxmData)
        assert 'extraction_error' in result.metadata
        assert 'Not a valid OLE2 file' in result.metadata['extraction_error']


@patch('os.path.exists', return_value=True)
@patch('olefile.isOleFile', return_value=True)
@patch('olefile.OleFileIO')
def test_read_txm_success(mock_olefile_io, mock_is_ole, mock_exists):
    """Test full metadata extraction and 3D data cataloging from a valid TXM file."""
    
    # 1. Setup the mock OLE file and its context manager
    mock_ole = MagicMock()
    mock_olefile_io.return_value.__enter__.return_value = mock_ole
    
    # 2. Mock the directory structure (listdir)
    mock_ole.listdir.return_value = [
        ['Version'],                            # Root level metadata
        ['ReconSettings', 'VoxelSize'],         # Reconstruction settings (Sub-directory)
        ['ReconSettings', 'FDK_Filter'],        # String-based recon setting
        ['ImageData1', 'Slice_001'],            # 3D block/slice data
        ['ImageData1', 'Slice_002'],            
        ['ImageData1', 'Slice_003'],            
    ]
    
    # 3. Mock the stream reading (openstream)
    def side_effect_openstream(path):
        mock_stream = MagicMock()
        
        if path == ['Version']:
            # Simulating a UTF-8 null-terminated string
            mock_stream.read.return_value = '16.2.1\x00'.encode('utf-8')
        elif path == ['ReconSettings', 'VoxelSize']:
            # Simulating a 4-byte float/int binary stream
            # Using 75.5 to avoid false-positive string decoding on standard ASCII bytes
            mock_stream.read.return_value = struct.pack('<f', 75.5)
        elif path == ['ReconSettings', 'FDK_Filter']:
            mock_stream.read.return_value = 'Shepp-Logan\x00'.encode('utf-8')
        else:
            # Fallback for empty/unhandled streams
            mock_stream.read.return_value = b''
            
        # Ensure the stream can be used as a context manager (`with ole.openstream...`)
        mock_stream.__enter__.return_value = mock_stream
        return mock_stream
        
    mock_ole.openstream.side_effect = side_effect_openstream
    
    # 4. Execute the reader
    result = read_txm('simulated_3d_volume.txm')
    
    # 5. Assertions
    assert isinstance(result, TxmData)
    assert 'extraction_error' not in result.metadata
    
    # Check Root Metadata
    assert result.metadata['Version'] == '16.2.1'

    # Check ReconSettings (Ensuring dual-decoding works on 4-byte blocks)
    assert 'VoxelSize' in result.recon_settings
    assert result.recon_settings['VoxelSize']['float32'] == 75.5    
    assert result.recon_settings['FDK_Filter'] == 'Shepp-Logan'
    
    # Check 3D Image Data Cataloging
    assert 'ImageData1' in result.image_data_summary
    assert result.image_data_summary['ImageData1'] == 3  # 3 slices mocked
    
    assert result.metadata['Total_ImageData_Folders'] == 1
    assert result.metadata['Total_3D_Slices_or_Blocks'] == 3