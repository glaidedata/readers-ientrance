import os
import pytest
import sqlite3
import struct
import numpy as np
from readers_ientrance.zmes_reader import read_zmes, ZmesDLSData

@pytest.fixture
def mock_zmes_file(tmp_path):
    """Dynamically generates a fake Malvern ZMES SQLite database for testing."""
    db_path = tmp_path / "dummy.zmes"
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Create the Malvern database schema
        cursor.execute("CREATE TABLE RecordParameterTypes (Id INTEGER, FriendlyName TEXT, UniformResourceName TEXT)")
        cursor.execute("CREATE TABLE StandardRecords (Id INTEGER, CreatedDateTime TEXT)")
        cursor.execute("CREATE TABLE RecordParameterData (RecordId INTEGER, ParameterTypeId INTEGER, Data_Blob BLOB, Data_Text TEXT, Data_Double REAL, Data_Int32 INTEGER, Data_Boolean INTEGER)")
        
        # 2. Insert dummy metadata mappings
        cursor.execute("INSERT INTO RecordParameterTypes VALUES (1, 'Correlation Data', 'SizeAnalysisResult.Data')")
        cursor.execute("INSERT INTO RecordParameterTypes VALUES (2, 'Sample Name', 'urn:Sample.Name')")
        cursor.execute("INSERT INTO StandardRecords VALUES (100, '2026-04-08 12:00:00')")
        
        # 3. Build a fake MS-NRBF strided blob (15 floats separated by 6 bytes of XML padding)
        blob_data = bytearray()
        for i in range(15):
            blob_data.extend(struct.pack('<d', float(i * 2.0))) # 8-byte float64
            blob_data.extend(b'\x06\x01\x01\x01\x02\x01')       # 6-byte XML padding
            
        # 4. Insert the data
        cursor.execute("INSERT INTO RecordParameterData (RecordId, ParameterTypeId, Data_Blob) VALUES (100, 1, ?)", (blob_data,))
        cursor.execute("INSERT INTO RecordParameterData (RecordId, ParameterTypeId, Data_Text) VALUES (100, 2, 'Fake Sample')")
        
        conn.commit()
        
    return str(db_path)

def test_missing_file_handling():
    """Ensure the reader handles non-existent files gracefully."""
    ghost_file = "non_existent_file.zmes"
    
    # 1. Ensure the file absolutely does not exist before testing
    if os.path.exists(ghost_file):
        os.remove(ghost_file)
        
    # 2. Run the reader
    data = read_zmes(ghost_file)
    
    # 3. Assertions
    assert isinstance(data, ZmesDLSData)
    assert len(data.records) == 0
    assert "extraction_error" in data.metadata
    assert "File not found" in data.metadata["extraction_error"]

def test_mock_zmes_parsing(mock_zmes_file):
    """Test data extraction using the dynamically generated dummy file."""
    data = read_zmes(mock_zmes_file)
    
    # Check Global Data
    assert isinstance(data, ZmesDLSData)
    assert data.metadata["File Format"] == "Malvern ZMES"
    assert "extraction_error" not in data.metadata
    
    # Check Record Extraction
    assert len(data.records) == 1
    record = data.records["Fake Sample"]
    
    # Check Metadata
    assert record.metadata["CreatedDateTime"] == "2026-04-08 12:00:00"
    assert record.metadata["Sample Name"] == "Fake Sample"
    
    # Check Array Striding Logic
    assert record.correlation_data is not None
    assert isinstance(record.correlation_data, np.ndarray)
    assert record.correlation_data.shape == (15,)
    assert record.correlation_data[1] == 2.0  # i * 2.0 where i=1
    assert record.correlation_data[-1] == 28.0 # i * 2.0 where i=14