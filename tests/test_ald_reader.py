import os
import pytest
import pandas as pd
from readers_ientrance.ald_reader import read_italya_ald, ALDData

# Define a fixture to get the path to the dummy data
@pytest.fixture
def dummy_ald_path():
    return os.path.join(os.path.dirname(__file__), "data", "dummy_ald.txt")

def test_read_italya_ald_extraction(dummy_ald_path):
    """Test that the ALD reader correctly parses the different sections of the log file."""
    data = read_italya_ald(dummy_ald_path)

    # 1. Test basic types and header info
    assert isinstance(data, ALDData)
    assert data.start_timestamp == "10.02.2026 15:33:22"
    assert data.system_name == "Italya ALD"

    # 2. Test System Configurations
    assert "Atmosphere Pressure" in data.metadata
    assert data.metadata["Atmosphere Pressure"] == "760"
    assert data.metadata["Vacuum Limit"] == "760"

    # 3. Test Port Configurations
    assert "Port 1" in data.port_configurations
    assert data.port_configurations["Port 1"] == "TMA"
    assert data.port_configurations["Port 2"] == "TDMASn"

    # 4. Test Precursor Doses
    assert "TMA" in data.precursor_doses
    assert data.precursor_doses["TMA"] == "11760milliseconds"
    assert data.precursor_doses["H₂O"] == "31565milliseconds"

    # 5. Test Running RCP
    assert len(data.running_rcp) == 3
    assert data.running_rcp[0] == ["1"]
    assert data.running_rcp[1] == ["2", "Heater", "1", "90", "°C"]
    assert data.running_rcp[2] == ["3", "Heater", "6", "90", "°C"]

    # 6. Test Communication Data (Pandas DataFrame)
    assert isinstance(data.communication_data, pd.DataFrame)
    assert not data.communication_data.empty
    assert len(data.communication_data) == 2
    
    # Check specific values in the DataFrame
    assert data.communication_data.iloc[0]["sensor"] == "Pressure"
    assert data.communication_data.iloc[0]["value"] == 176.0
    assert data.communication_data.iloc[1]["sensor"] == "RotationMotor"
    assert data.communication_data.iloc[1]["value"] == 668.9

def test_read_italya_ald_file_not_found():
    """Test that the reader raises a FileNotFoundError for an invalid path."""
    with pytest.raises(FileNotFoundError):
        read_italya_ald("this_file_does_not_exist.txt")