import numpy as np
import pytest
from readers_ientrance.ta_dsc_reader import read_ta_dsc

@pytest.fixture
def mock_ta_dsc_file(tmp_path):
    """Creates a temporary TA Instruments DSC .txt file for testing."""
    content = """CLOSED
Version	2.0
Language	English
Mode	Standard
Run	1
RunSerial	1030
Instrument	DSC Q2000 V24.11 Build 124
Module	DSC Standard Cell RC
Operator
File	\\\\U2\\ta\\Data\\DSC\\Misure2026\\ProveAlessia\\Zeolite 13X\\Pan and lid_Heat-Isotherm 3h 550_cool.001
ProcName	Cyclic
InstSerial	2000-2514
Sample	Zeolite
Size	28.0000	mg
PanMass	11.000 10.900  mg
PanResist	Automatic Automatic  K/W
PanFactor	Default Default
Method	Cyclic
Comment
Xcomment	Pan: None
Xcomment	Gas1: Air 50.0 ml/min
Xcomment	Gas2: Air 50.0 ml/min
Text
Exotherm	UP
Kcell	1.00000
Cpconst	Standard: 1.000
Calib	0.0000
TempCal	0	pts
TzeroDt	9.9016 -0.0036 -5.4387
TzeroDtz	9.9016 0.0325 5.8678
InstCalFile	Tzero: \\\\U2\\ta\\Data\\DSC\\Misure2025\\Tzero\\CALIBRATION\\4050_RCS (90)_01_20_2026 13_42_03.TZR
InstCalFile	Baseline: \\\\U2\\ta\\Data\\DSC\\Misure2025\\Tzero\\Tzero_cell.078
InstCalFile	Sapphire: \\\\U2\\ta\\Data\\DSC\\Misure2025\\Tzero\\Tzero_crogioli.015
InstCalDate	Tzero 2026-01-20 Time 13:42:03
TempRange	9.92 to 79.11 °C at 4.99 °C/min Heat Only
AutoZero	Delta T Offset 0.000 uV
AutoZero	Delta T0 Offset 0.000 uV
MultiptCal	0
MultiPtDesc	0) Not set
AutoCellConst	Calibration Date 2024-11-29 11:54:11
Controls	Gas 1  Event Off  Sampling 0.2
Cell#	RC-04050
CoolingUnit	RCS (90)
SelHeatFlow	Heat Flow T4P (mW)
AutoLidII	Installed
AutoAnalysis	Off
MacroFile
Nsig	5
Sig1	Time (min)
Sig2	Temperature (°C)
Sig3	Heat Flow (mW)
Sig4	Heat Capacity (mJ/°C)
Sig5	Sample Purge Flow (mL/min)
Date	2026-03-09
Time	10:48:37
OrgMethod	1: Ramp 5.00 °C/min to 550.00 °C
OrgMethod	2: Isothermal for 180.00 min
OrgMethod	3: Ramp 5.00 °C/min to 200.00 °C
OrgMethod	4: Isothermal for 30.00 min
OrgFile	\\\\u2\\ta\\Data\\DSC\\Misure2026\\ProveAlessia\\Zeolite 13X\\Pan and lid_Heat-Isotherm 3h 550_cool.001
StartOfData
4.99994E-4	69.41475	-5.384774	0.0000000	49.99391
0.01216666	69.41914	-5.344699	225.8698	50.00804
0.03050000	69.42689	-5.270264	212.6972	50.00088
0.04716666	69.44108	-5.203757	172.5238	49.99924
"""
    file_path = tmp_path / "mock_ta_dsc.txt"
    file_path.write_text(content, encoding="utf-8")
    return str(file_path)


def test_read_ta_dsc(mock_ta_dsc_file):
    """Validates the output of the TA reader against the mock file."""

    # 1. Read the data
    dsc_data = read_ta_dsc(mock_ta_dsc_file)

    # 2. Validate Root Metadata Extraction
    assert dsc_data.metadata.get("Instrument") == "DSC Q2000 V24.11 Build 124"
    assert dsc_data.metadata.get("Sample") == "Zeolite"
    assert dsc_data.metadata.get("Size") == "28.0000	mg"
    assert dsc_data.metadata.get("Date") == "2026-03-09"

    # Verify concatenated duplicate keys (e.g. Xcomment)
    assert "Gas1: Air 50.0 ml/min" in dsc_data.metadata.get("Xcomment", "")
    assert "Gas2: Air 50.0 ml/min" in dsc_data.metadata.get("Xcomment", "")

    # 3. Validate Method Steps (OrgMethod Extraction)
    assert len(dsc_data.method_steps) == 4
    assert dsc_data.method_steps[0] == "1: Ramp 5.00 °C/min to 550.00 °C"
    assert dsc_data.method_steps[-1] == "4: Isothermal for 30.00 min"

    # 4. Validate Data and Dynamic Column Routing
    assert dsc_data.data is not None
    assert len(dsc_data.data) == 4  # 4 rows of mock data

    # Verify that 'Sig' headers dynamically mapped correctly to the arrays
    assert np.allclose(dsc_data.time[0], 4.99994E-4)
    assert np.allclose(dsc_data.sample_temperature[0], 69.41475)
    assert np.allclose(dsc_data.heat_flow[0], -5.384774)
    assert np.allclose(dsc_data.heat_capacity[1], 225.8698)  # Checking row 2 for heat capacity
    assert np.allclose(dsc_data.approx_gas_flow[-1], 49.99924)  # Checking row 4 for purge flow