from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from readers_ientrance.spc_reader import read_spc


@patch('readers_ientrance.spc_reader.spc.File')
def test_read_spc_single_spectrum(mock_spc_file):
    """Verifies that a single-point .spc file is parsed and flattened to 1D."""
    
    # 1. Setup mock SPC file structure
    mock_f = MagicMock()
    mock_f.x = np.linspace(100, 3000, 100)
    
    # Mocking metadata, including a byte-string to test our decoding logic
    mock_f.fversn = b'0x4B\x00'
    mock_f.fexper = 'Raman'
    
    # Mock a single subfile containing the y-data
    mock_sub = MagicMock()
    mock_sub.y = np.ones(100)
    mock_sub.subfile_label = b'Point_1'
    mock_f.sub = [mock_sub]

    mock_spc_file.return_value = mock_f

    # 2. Execute reader
    data = read_spc('dummy.spc')

    # 3. Assertions for Data Arrays
    assert data.x_data is not None
    assert len(data.x_data) == 100

    assert data.spectra is not None
    # Because there is only 1 subfile, it should flatten to 1D
    assert data.spectra.shape == (100,)

    # 4. Assertions for Metadata
    assert data.metadata['number_of_subfiles'] == 1
    # Check that bytes were cleanly decoded to strings and stripped of null chars
    assert data.metadata['fversn'] == '0x4B'
    assert data.metadata['fexper'] == 'Raman'
    
    # Check subfile metadata extraction
    assert 'subfile_metadata' in data.metadata
    assert len(data.metadata['subfile_metadata']) == 1
    assert data.metadata['subfile_metadata'][0]['subfile_label'] == 'Point_1'


@patch('readers_ientrance.spc_reader.spc.File')
def test_read_spc_mapping(mock_spc_file):
    """Verifies that a multi-subfile .spc file is parsed into a 2D array."""
    
    mock_f = MagicMock()
    mock_f.x = np.linspace(100, 3000, 100)
    
    # Create 5 subfiles to simulate a depth series or map
    mock_f.sub = []
    for i in range(5):
        mock_sub = MagicMock()
        mock_sub.y = np.ones(100) * i  # Give each a different intensity
        mock_f.sub.append(mock_sub)

    mock_spc_file.return_value = mock_f

    # Execute reader
    data = read_spc('dummy_map.spc')

    # Assertions
    assert data.spectra is not None
    # Should be a 2D array: (5 subfiles, 100 points)
    assert data.spectra.shape == (5, 100)
    assert data.metadata['number_of_subfiles'] == 5


def test_spc_missing_dependency():
    """Verifies that a helpful error is raised if the spc library is not installed."""
    
    # Temporarily patch the spc module to be None
    with patch('readers_ientrance.spc_reader.spc', None):
        with pytest.raises(ImportError, match="The 'spc' package is required"):
            read_spc('dummy.spc')