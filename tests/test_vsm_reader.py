import os
import numpy as np
from readers_ientrance import read_lakeshore_vsm, VSMData

# Get the absolute path to the dummy data file
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
DUMMY_FILE = os.path.join(TEST_DIR, "data", "dummy_vsm.csv")


def test_read_lakeshore_vsm_metadata():
    """Test that the reader correctly extracts metadata and flags."""
    result = read_lakeshore_vsm(DUMMY_FILE)

    # Check that it returns our strict Pydantic model
    assert isinstance(result, VSMData)

    # Check tricky metadata parsing
    assert result.metadata["Software Version"] == "Version 1.4.2"
    assert result.metadata["Measurement Type"] == "FORC"

    # Check standard colon-separated metadata
    assert result.metadata["ID"] == "Dummy_Sample_001"
    assert result.metadata["Mass"] == "0.123"


def test_read_lakeshore_vsm_data_arrays():
    """Test that the reader correctly maps CSV columns to NumPy arrays."""
    result = read_lakeshore_vsm(DUMMY_FILE)

    # Check array shapes (we have 3 rows of data)
    assert len(result.step) == 3
    assert len(result.magnetic_field) == 3

    # Check specific numerical mapping
    np.testing.assert_array_almost_equal(result.magnetic_field, [100.5, 200.0, 300.5])
    np.testing.assert_array_almost_equal(
        result.magnetic_moment, [0.0015, 0.0030, 0.0045]
    )

    # Check string mapping
    assert result.field_status[0] == "OK"
