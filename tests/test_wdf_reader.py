import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from readers_ientrance.wdf_reader import read_renishaw_wdf

# Patch the WDFReader inside wdf_reader
@patch('readers_ientrance.wdf_reader.WDFReader')
def test_read_renishaw_wdf_mocked(MockWDFReader):
    """
    Tests the read_renishaw_wdf function without needing a physical .wdf file
    by mocking the renishawWiRE.WDFReader behavior.
    """
    # 1. Setup our "Fake" WDFReader instance
    mock_instance = MagicMock()
    
    # Give it dummy metadata similar to what the client described
    mock_instance.measurement_type = 3 
    mock_instance.laser_length = 457.0
    mock_instance.title = "Mock Map 11x11"
    mock_instance.accumulation_count = 5
    
    # Give it dummy numpy arrays 
    mock_instance.xdata = np.linspace(100, 3000, 1024)  
    mock_instance.spectra = np.random.rand(11, 11, 1024) 
    mock_instance.xpos = np.arange(11)
    mock_instance.ypos = np.arange(11)
    mock_instance.zpos = None
    
    mock_instance.img = None
    
    # Tell the Mock object to return our fake instance when instantiated
    MockWDFReader.return_value = mock_instance

    # 2. Call our reader function. 
    data = read_renishaw_wdf("fake_path_that_does_not_exist.wdf")

    # 3. Assertions to ensure our Pydantic model captured the mocked data correctly
    assert data.metadata is not None
    assert data.metadata.get("File Format") == "Renishaw WDF"
    assert data.metadata.get("laser_length") == 457.0
    assert data.metadata.get("title") == "Mock Map 11x11"
    
    assert data.wavenumber is not None
    assert data.wavenumber.shape == (1024,)
    
    assert data.spectra is not None
    assert data.spectra.shape == (11, 11, 1024)
    
    assert data.xpos is not None
    assert len(data.xpos) == 11