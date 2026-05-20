import pytest
import numpy as np
import pandas as pd
from readers_ientrance.dsc_reader import read_perkinelmer_dsc, DSCData

# The embedded mock content from your short.txt file
MOCK_DSC_TXT = """Filename:	c:\\users\\sanchirico\\desktop\\gianluca\\dna_2_5_h_1.ds8d 
Operator ID:	 
Sample ID:	 
Comment: 	m(S+PAN)= 616.98 mg

m(R+PAN)= 616.53 mg

m(R+PAN-GAS)= 616.42 mg 
Serial Number:	 
Data Collected:	27/10/2025 12:17:34 
Sample Weight:	1.080 mg 
Display Weight:	1.080 
Validation 
Validated:	No 
By:	 
Date:	 
Calibration Information 
Filename:	C:\\Program Files (x86)\\PerkinElmer\\Pyris\\Calibrations\\HP\\HP_2_5.ds8c 
Date/Time:	23/06/2025 17:10:53 
Initial Conditions 
Temperature:	 165.00 °C 
Purge Gas:	 
Purge Gas Rate:	 
Baseline Filename:	 
End Condition:	Go To Load 
Total Points in Run:	33254 
Method Steps: 
Pre-Run Actions 
Switch the Gas to Nitrogen at 20.0 ml/min  
	Action occurs Immediately 
Start the Run 
	Action occurs Immediately 
1)	Hold for 1.0 min at 165.00°C 
 
2)	Heat from 165.00°C to 425.00°C at 2.50°C/min 
 
1) DSC 8500 Isothermal 
	Time     
	Unsubtracted	Baseline     	Program     	Sample     	Approx.
Heat Flow     	Uncorrected 
	          	Heat Flow     	Heat Flow     	Temperature	Temperature	Gas Flow     	Calibration	Heat Flow      
	0.000000	-30.724099	0.000000	165.000000	159.445000	0.000000	1.369764	-30.724099 
	0.000500	-30.741769	0.000000	165.000000	159.541000	0.000000	1.369764	-30.741769 
	0.001000	-30.739988	0.000000	165.000000	159.641000	0.000000	1.369764	-30.739988 
 
	DSC8500 MANUAL TUNE CALIBRATION VALUES: 
Date: 27/10/2025 10:06:34 
Slope: 61 
Coarse Balance: -5 
Fine Balance: 0 
 
	PROFILE VALUES FOR THIS DATA: 
 
Software Version	13.3.2.0030 
Firmware Version	Part Number N5368010  Revision 0.01: Build 4 
Instrument Serial Number	 
Load Temperature	25.0 °C 
Go To Temp Rate	200.0 °C/min 
Maximum Allowed Temperature	600.0 °C 
Helium Purge	Was Not Used 
Liquid Nitrogen	Was Not Used 
Data taken using the	Normal Range 
Filter Factor	0 
Cooling Device	Intracooler II 
Wavelet Denoising used: No 
Autoslope Used: No
"""

@pytest.fixture
def mock_dsc_file(tmp_path):
    """Creates a temporary txt file for testing using Pytest's built-in tmp_path."""
    file_path = tmp_path / "Run_2_5_mock.txt"
    file_path.write_text(MOCK_DSC_TXT, encoding="utf-8")
    return str(file_path)

def test_read_perkinelmer_dsc(mock_dsc_file):
    """Validates the output of the reader against the mock file."""
    
    # 1. Read the data
    dsc_data = read_perkinelmer_dsc(mock_dsc_file)
    
    # 2. Validate the Return Type
    assert isinstance(dsc_data, DSCData)
    
    # 3. Validate Top Metadata Extraction
    assert "Filename" in dsc_data.metadata
    assert "dna_2_5_h_1.ds8d" in dsc_data.metadata["Filename"]
    assert dsc_data.metadata.get("Sample Weight") == "1.080 mg"
    assert dsc_data.metadata.get("Data Collected") == "27/10/2025 12:17:34"
    
    # 4. Validate Multiline Comment
    comment = dsc_data.metadata.get("Comment", "")
    assert "m(S+PAN)= 616.98 mg" in comment
    assert "m(R+PAN)= 616.53 mg" in comment
    assert "m(R+PAN-GAS)= 616.42 mg" in comment

    # 5. Validate Method Steps Recipe
    assert len(dsc_data.method_steps) > 0
    assert "Pre-Run Actions" in dsc_data.method_steps
    assert "1)\tHold for 1.0 min at 165.00°C" in dsc_data.method_steps
    
    # 6. Validate DataFrame parsing (Data Block)
    df = dsc_data.data
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert len(df) == 3  # The mock contains exactly 3 valid data rows
    assert len(df.columns) == 8 # Expected to have 8 columns
    
    # 7. Validate the extracted Numpy Arrays
    assert isinstance(dsc_data.time, np.ndarray)
    assert len(dsc_data.time) == 3
    assert dsc_data.time[0] == 0.000000
    
    assert isinstance(dsc_data.sample_temperature, np.ndarray)
    assert dsc_data.sample_temperature[0] == 159.445000
    
    assert isinstance(dsc_data.unsubtracted_heat_flow, np.ndarray)
    assert dsc_data.unsubtracted_heat_flow[0] == -30.724099
    
    # 8. Validate Footer / Profile Values
    assert "Footer_Date" in dsc_data.metadata
    assert dsc_data.metadata["Footer_Date"] == "27/10/2025 10:06:34"
    assert "Footer_Slope" in dsc_data.metadata
    assert dsc_data.metadata["Footer_Slope"] == "61"
    assert "Footer_Software Version" in dsc_data.metadata
    assert dsc_data.metadata["Footer_Software Version"] == "13.3.2.0030"
    assert "Footer_Cooling Device" in dsc_data.metadata
    assert dsc_data.metadata["Footer_Cooling Device"] == "Intracooler II"