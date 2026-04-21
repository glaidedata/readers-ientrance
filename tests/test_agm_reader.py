import os
import numpy as np
import pandas as pd
from readers_ientrance import read_micromag_agm

# Get the absolute path to the dummy data file
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
DUMMY_FILE = os.path.join(TEST_DIR, "data", "dummy_agm.txt")


def test_read_micromag_agm_metadata():
    """Test that the reader correctly extracts metadata and those tricky first 2 lines."""
    result = read_micromag_agm(DUMMY_FILE)

    # Check the custom extracted headers
    assert result["metadata"]["Instrument Model"] == "MicroMag 2900/3900"
    assert result["metadata"]["Data Format Version"] == "0016.002"
    assert result["metadata"]["Measurement Type"] == "Direct moment vs. field"
    assert result["metadata"]["Measurement Mode"] == "Multiple segments"

    # Check standard spaced metadata
    assert result["metadata"]["Configuration"] == "AGM"
    assert result["metadata"]["Operating frequency"] == "+406.5000E+00"
    assert result["metadata"]["Number of segments"] == "7"


def test_read_micromag_agm_segments():
    """Test that the reader correctly extracts the segment table into a DataFrame."""
    result = read_micromag_agm(DUMMY_FILE)

    seg_df = result["segments"]

    # Check that it is a pandas DataFrame
    assert isinstance(seg_df, pd.DataFrame)

    # Check that it extracted the expected number of segments (7 based on the dummy file)
    assert len(seg_df) == 7

    # Check a specific value in the first row
    assert seg_df.iloc[0]["Segment Number"] == 1
    assert seg_df.iloc[0]["Final Field (Oe)"] == 5000.0


def test_read_micromag_agm_data_arrays():
    """Test that the reader correctly maps comma-separated data to arrays."""
    result = read_micromag_agm(DUMMY_FILE)

    # Check array lengths (assuming you put 3 data rows in your dummy file)
    assert len(result["magnetic_field"]) == 3
    assert len(result["magnetic_moment"]) == 3
    assert len(result["normalized_moment"]) == 3

    # Check specific numerical mapping from the first row of your real file
    # +5.005130E+03, +333.3056E-06, +998.3703E-03
    np.testing.assert_array_almost_equal(result["magnetic_field"][0], 5005.130)
    np.testing.assert_array_almost_equal(result["magnetic_moment"][0], 0.0003333056)
    np.testing.assert_array_almost_equal(result["normalized_moment"][0], 0.9983703)
