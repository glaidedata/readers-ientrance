import struct
from unittest.mock import MagicMock, patch

import numpy as np
from readers_ientrance.txm_reader import TxmData, read_txm


def _mock_stream(data):
    stream = MagicMock()
    stream.read.return_value = data
    stream.__enter__.return_value = stream
    return stream


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
    assert result.preview_image is None
    mock_ole.get_size.assert_not_called()


@patch('os.path.exists', return_value=True)
@patch('olefile.isOleFile', return_value=True)
@patch('olefile.OleFileIO')
def test_read_txm_extracts_middle_slice_from_discovered_streams(
    mock_olefile_io, mock_is_ole, mock_exists
):
    """Preview selection uses discovered, naturally ordered complete stream paths."""
    mock_ole = MagicMock()
    mock_olefile_io.return_value.__enter__.return_value = mock_ole
    mock_ole.listdir.return_value = [
        ['ImageData2', 'Slice_003'],
        ['ImageInfo', 'ImageHeight'],
        ['ImageData1', 'Slice_001'],
        ['ImageData2', 'Slice_002'],
        ['ImageInfo', 'ImageWidth'],
    ]

    middle_slice = np.array([[10, 11], [12, 13]], dtype=np.uint16)
    stream_data = {
        ('ImageInfo', 'ImageWidth'): struct.pack('<i', 2),
        ('ImageInfo', 'ImageHeight'): struct.pack('<i', 2),
        ('ImageData2', 'Slice_002'): middle_slice.tobytes(),
    }
    mock_ole.openstream.side_effect = lambda path: _mock_stream(
        stream_data[tuple(path)]
    )
    mock_ole.get_size.side_effect = lambda path: {
        ('ImageData1', 'Slice_001'): 8,
        ('ImageData2', 'Slice_002'): 8,
        ('ImageData2', 'Slice_003'): 8,
    }[tuple(path)]

    result = read_txm('simulated_3d_volume.txm', include_preview=True)

    np.testing.assert_array_equal(result.preview_image, middle_slice)
    assert result.preview_slice_index == 1
    assert result.preview_stream_path == ['ImageData2', 'Slice_002']
    assert result.preview_plane_index == 0
    assert result.preview_error is None
    assert result.image_data_summary == {'ImageData1': 1, 'ImageData2': 2}


@patch('os.path.exists', return_value=True)
@patch('olefile.isOleFile', return_value=True)
@patch('olefile.OleFileIO')
def test_read_txm_preview_supports_existing_image_number_streams(
    mock_olefile_io, mock_is_ole, mock_exists
):
    """The reader preserves support for ImageData*/ImageN TXM layouts."""
    mock_ole = MagicMock()
    mock_olefile_io.return_value.__enter__.return_value = mock_ole
    mock_ole.listdir.return_value = [
        ['ImageData1', 'Image10'],
        ['ImageInfo', 'ImageWidth'],
        ['ImageData1', 'Image2'],
        ['ImageData1', 'Image1'],
        ['ImageInfo', 'ImageHeight'],
    ]

    middle_slice = np.array([[10, 11], [12, 13]], dtype=np.uint16)
    stream_data = {
        ('ImageInfo', 'ImageWidth'): struct.pack('<i', 2),
        ('ImageInfo', 'ImageHeight'): struct.pack('<i', 2),
        ('ImageData1', 'Image2'): middle_slice.tobytes(),
    }
    mock_ole.openstream.side_effect = lambda path: _mock_stream(
        stream_data[tuple(path)]
    )
    mock_ole.get_size.side_effect = lambda path: 8

    result = read_txm('existing_image_number_layout.txm', include_preview=True)

    np.testing.assert_array_equal(result.preview_image, middle_slice)
    assert result.preview_stream_path == ['ImageData1', 'Image2']


@patch('os.path.exists', return_value=True)
@patch('olefile.isOleFile', return_value=True)
@patch('olefile.OleFileIO')
def test_read_txm_extracts_middle_slice_from_multiplane_stream(
    mock_olefile_io, mock_is_ole, mock_exists
):
    """Middle-plane selection accounts for streams containing multiple planes."""
    mock_ole = MagicMock()
    mock_olefile_io.return_value.__enter__.return_value = mock_ole
    mock_ole.listdir.return_value = [
        ['ImageInfo', 'ImageWidth'],
        ['ImageInfo', 'ImageHeight'],
        ['ImageData1', 'Block_1'],
        ['ImageData2', 'Block_2'],
    ]

    first_block = np.array([[[0, 1], [2, 3]]], dtype=np.uint16)
    second_block = np.array(
        [
            [[10, 11], [12, 13]],
            [[20, 21], [22, 23]],
            [[30, 31], [32, 33]],
        ],
        dtype=np.uint16,
    )
    stream_data = {
        ('ImageInfo', 'ImageWidth'): struct.pack('<i', 2),
        ('ImageInfo', 'ImageHeight'): struct.pack('<i', 2),
        ('ImageData2', 'Block_2'): second_block.tobytes(),
    }
    mock_ole.openstream.side_effect = lambda path: _mock_stream(
        stream_data[tuple(path)]
    )
    mock_ole.get_size.side_effect = lambda path: {
        ('ImageData1', 'Block_1'): first_block.nbytes,
        ('ImageData2', 'Block_2'): second_block.nbytes,
    }[tuple(path)]

    result = read_txm('simulated_block_volume.txm', include_preview=True)

    np.testing.assert_array_equal(result.preview_image, second_block[1])
    assert result.preview_slice_index == 2
    assert result.preview_stream_path == ['ImageData2', 'Block_2']
    assert result.preview_plane_index == 1
    assert result.preview_error is None


@patch('os.path.exists', return_value=True)
@patch('olefile.isOleFile', return_value=True)
@patch('olefile.OleFileIO')
def test_read_txm_preview_requires_verified_dimensions(
    mock_olefile_io, mock_is_ole, mock_exists
):
    """Preview extraction does not invent dimensions absent from TXM metadata."""
    mock_ole = MagicMock()
    mock_olefile_io.return_value.__enter__.return_value = mock_ole
    mock_ole.listdir.return_value = [['ImageData1', 'Slice_001']]

    result = read_txm('missing_dimensions.txm', include_preview=True)

    assert result.preview_image is None
    assert result.preview_error == 'Missing valid ImageWidth or ImageHeight metadata.'
    mock_ole.get_size.assert_not_called()
    mock_ole.openstream.assert_not_called()


@patch('os.path.exists', return_value=True)
@patch('olefile.isOleFile', return_value=True)
@patch('olefile.OleFileIO')
def test_read_txm_preview_failure_does_not_fail_metadata_extraction(
    mock_olefile_io, mock_is_ole, mock_exists
):
    """An unreadable image stream leaves metadata parsing successful."""
    mock_ole = MagicMock()
    mock_olefile_io.return_value.__enter__.return_value = mock_ole
    mock_ole.listdir.return_value = [
        ['ImageInfo', 'ImageWidth'],
        ['ImageInfo', 'ImageHeight'],
        ['ImageData1', 'Slice_001'],
    ]
    stream_data = {
        ('ImageInfo', 'ImageWidth'): struct.pack('<i', 2),
        ('ImageInfo', 'ImageHeight'): struct.pack('<i', 2),
    }
    mock_ole.openstream.side_effect = lambda path: _mock_stream(
        stream_data[tuple(path)]
    )
    mock_ole.get_size.side_effect = OSError('unreadable stream')

    result = read_txm('unreadable_stream.txm', include_preview=True)

    assert 'extraction_error' not in result.metadata
    assert result.preview_image is None
    assert result.preview_error == 'No ImageData stream contains complete uint16 image planes.'
