import pytest
import numpy as np
import pandas as pd
from readers_ientrance.thermal_reader import read_thermal_dat, ThermalData

# A truncated mock based on your Cu TEC VerAcc.txt file
MOCK_DAT_CONTENT = """[Header]
TITLE,Cu TEC VerAcc
DATATYPE,TIME,1
DATATYPE,COMMENT,2
[Data]
TimeStamp (sec),Comment,System Temperature (K),Field (Oe),Chamber Pres (torr),Temperature Status (code),Field Status (code),Chamber Status (code),Bridge Cycle (count),Therm Resistance (ohms),Therm Resistance Rate (ohms/sec),Field Rate (Oe/sec),Cell Imbalance (ppm),Cell Imbalance Rate (ppm/sec),Tap Imbalance (ppm),Coarse DAC Imbalance (ppm),Fine DAC Imbalance (ppm),Loop Imbalance (ppm),Sample Temperature (K),Sample Temperature Rate (K/sec),Dilation (ppm),Dilation Rate (ppm/sec),Rotator Angle (deg),Sample Temperature Range (K),Therm Exp Coeff Raw (ppm/K),Therm Exp Coeff (ppm/K),Therm Exp Coeff Compare (ppm/K),Therm Expansion Coeff Diff (%),Therm Expansion Coeff Diff (abs),Therm Exp Coeff Baseline (ppm/K),Therm Exp Coeff Reference (ppm/K)
3924947993.08362,BEGIN:PARAMS,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
3924947993.08362,cell_constant=0.168797183478752,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
3924947993.08362,sample_length=1.956,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
3924947993.08362,offset_mode=set,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
3924947993.08362,END:PARAMS,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
3924948063.34094,,399.345724998808,0.04912863890149,8.32299455399617,6,4,1,19275,66.14954207888,0.000239036830615191,-0.00176645153232089,-225200.015548035,-0.133118373923935,-226562.5,1297.81162831932,64.6728236461058,0.086751950828315,399.247460967162,-0.00159159469604039,-19434.1146952349,-0.0114877334292595,0,0.0149478062999719,7.21775051012609,8.15609231750389,17.5038244417548,-53.4039412664138,-9.34773212425091,-0.328635485104428,0.609706322273368
3924948073.34568,,399.245340346411,0.0540654267609365,8.32413302769497,6,4,1,19294,66.1521239437161,0.000265407921276051,-0.0052977042943646,-225201.653507611,-0.18755927158054,-226562.5,1297.81162831932,63.0348640697775,0.127164207583348,399.230648002688,-0.00185644983887198,-19434.256046443,-0.0161858265736817,0,0.0179660624619942,8.71869857982081,9.65723378698449,17.5036863934635,-44.8274290917892,-7.84645260647901,-0.328835417465143,0.609699789698535
"""

@pytest.fixture
def mock_thermal_file(tmp_path):
    """Creates a temporary dat file for testing using Pytest's built-in tmp_path."""
    file_path = tmp_path / "dummy_thermal.dat"
    file_path.write_text(MOCK_DAT_CONTENT, encoding="utf-8")
    return str(file_path)

def test_read_thermal_dat(mock_thermal_file):
    """Validates the output of the reader against the mock file."""
    
    # 1. Read the data
    thermal_data = read_thermal_dat(mock_thermal_file)
    
    # 2. Validate the Return Type
    assert isinstance(thermal_data, ThermalData)
    
    # 3. Validate Header Metadata Extraction
    assert "TITLE" in thermal_data.metadata
    assert thermal_data.metadata["TITLE"] == "Cu TEC VerAcc"
    
    # 4. Validate Embedded Parameters Extraction (from the BEGIN/END PARAMS block)
    assert "cell_constant" in thermal_data.metadata
    assert thermal_data.metadata["cell_constant"] == "0.168797183478752"
    assert "sample_length" in thermal_data.metadata
    assert thermal_data.metadata["sample_length"] == "1.956"
    assert "offset_mode" in thermal_data.metadata
    assert thermal_data.metadata["offset_mode"] == "set"
    
    # 5. Validate DataFrame parsing
    df = thermal_data.data
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert len(df) == 2  # The mock contains exactly two valid rows after the PARAMS block
    assert "TimeStamp (sec)" in df.columns
    assert "System Temperature (K)" in df.columns
    assert "Dilation (ppm)" in df.columns
    
    # 6. Validate the extracted Numpy Arrays
    assert isinstance(thermal_data.time_stamp, np.ndarray)
    assert len(thermal_data.time_stamp) == 2
    assert thermal_data.time_stamp[0] == 3924948063.34094
    
    assert isinstance(thermal_data.system_temperature, np.ndarray)
    assert thermal_data.system_temperature[0] == 399.345724998808
    
    assert isinstance(thermal_data.dilation, np.ndarray)
    assert thermal_data.dilation[0] == -19434.1146952349