import sqlite3
import struct
import os
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional

# --- PYDANTIC MODELS ---

class ZmesRecord(BaseModel):
    """Holds structured data for a single DLS/Zeta measurement record."""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Core Arrays
    correlation_lag_times: Optional[np.ndarray] = None
    correlation_data: Optional[np.ndarray] = None
    
    size_classes: Optional[np.ndarray] = None
    intensity_distribution: Optional[np.ndarray] = None
    volume_distribution: Optional[np.ndarray] = None
    number_distribution: Optional[np.ndarray] = None
    
    zeta_potentials_x: Optional[np.ndarray] = None
    zeta_potential_distribution: Optional[np.ndarray] = None
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

class ZmesDLSData(BaseModel):
    """Main model for the entire Malvern .zmes file."""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    records: Dict[str, ZmesRecord] = Field(default_factory=dict)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


# --- HELPER FUNCTIONS ---

def _decode_blob(blob: bytes) -> Optional[np.ndarray]:
    if not blob or len(blob) < 80:
        return None
        
    is_single = b'System.Single' in blob
    dtype = '<f4' if is_single else '<f8'
    element_size = 4 if is_single else 8
    
    best_arr = None
    max_len = 0
    
    # Test strides from contiguous (8 bytes) up to heavily boxed lists (e.g., 8 + 12 bytes)
    for stride in range(element_size, element_size + 16):
        for offset in range(stride):
            num_elements = (len(blob) - offset) // stride
            if num_elements < 10:
                continue
                
            try:
                arr = np.ndarray(
                    shape=(num_elements,), 
                    dtype=dtype, 
                    buffer=blob, 
                    offset=offset, 
                    strides=(stride,)
                )
            except ValueError:
                continue
            
            # Check for physically realistic DLS numbers
            with np.errstate(invalid='ignore'):
                valid = np.isfinite(arr) & (np.abs(arr) < 1e15) & ((np.abs(arr) > 1e-30) | (arr == 0.0))
                
            padded = np.pad(valid, (1, 1), mode='constant')
            edges = np.diff(padded.astype(int))
            starts = np.where(edges == 1)[0]
            ends = np.where(edges == -1)[0]
            
            if len(starts) > 0:
                lengths = ends - starts
                best_idx = np.argmax(lengths)
                streak_len = lengths[best_idx]
                
                if streak_len > max_len and streak_len >= 10:
                    max_len = streak_len
                    best_arr = arr[starts[best_idx] : ends[best_idx]].copy()
                    
    return best_arr

# --- MAIN READER ---

def read_zmes(file_path: str) -> ZmesDLSData:
    file_metadata = {
        "File Format": "Malvern ZMES",
        "Parser": "sqlite3 / pandas payload scanner"
    }
    records = {}

    if not os.path.exists(file_path):
        file_metadata["extraction_error"] = f"File not found: {file_path}"
        return ZmesDLSData(metadata=file_metadata, records=records)

    try:
        with sqlite3.connect(file_path) as conn:
            
            types_query = "SELECT Id, FriendlyName, UniformResourceName FROM RecordParameterTypes"
            types_df = pd.read_sql_query(types_query, conn)
            
            id_to_name = dict(zip(types_df['Id'], types_df['FriendlyName']))
            id_to_urn = dict(zip(types_df['Id'], types_df['UniformResourceName']))

            records_query = "SELECT Id, CreatedDateTime FROM StandardRecords"
            records_df = pd.read_sql_query(records_query, conn)
            
            data_query = """
                SELECT RecordId, ParameterTypeId, Data_Blob, Data_Text, Data_Double, Data_Int32, Data_Boolean 
                FROM RecordParameterData
                WHERE Data_Blob IS NOT NULL 
                   OR Data_Text IS NOT NULL 
                   OR Data_Double IS NOT NULL 
                   OR Data_Int32 IS NOT NULL
                   OR Data_Boolean IS NOT NULL
            """
            data_df = pd.read_sql_query(data_query, conn)

            grouped = data_df.groupby('RecordId')
            
            for record_id, group in grouped:
                record_model = ZmesRecord()
                
                creation_time = records_df.loc[records_df['Id'] == record_id, 'CreatedDateTime'].values
                if len(creation_time) > 0:
                    record_model.metadata['CreatedDateTime'] = str(creation_time[0])
                
                for _, row in group.iterrows():
                    param_id = row['ParameterTypeId']
                    friendly_name = id_to_name.get(param_id, f"Unknown_Param_{param_id}")
                    urn = id_to_urn.get(param_id, "")
                    
                    if row['Data_Blob'] is not None:
                        array_data = _decode_blob(row['Data_Blob'])
                        
                        if array_data is not None:
                            if "SizeData.CorrelationLagTimes" in urn:
                                record_model.correlation_lag_times = array_data
                            elif "SizeAnalysisResult.Data" in urn or "AverageNormalisedCorrelationFunction" in urn:
                                record_model.correlation_data = array_data
                            elif "SizeAnalysisResult.Intensities" in urn:
                                record_model.intensity_distribution = array_data
                            elif "SizeAnalysisResult.Volumes" in urn:
                                record_model.volume_distribution = array_data
                            elif "SizeAnalysisResult.Numbers" in urn:
                                record_model.number_distribution = array_data
                            elif "ZetaAnalysisResult.ZetaPotentials" in urn:
                                record_model.zeta_potentials_x = array_data
                            elif "ZetaAnalysisResult.Intensities" in urn:
                                record_model.zeta_potential_distribution = array_data
                            else:
                                record_model.metadata[friendly_name] = f"<Decoded Array: {array_data.shape} {array_data.dtype}>"
                        else:
                            record_model.metadata[friendly_name] = f"<Unparsed Binary: {len(row['Data_Blob'])} bytes>"
                            
                    else:
                        if pd.notna(row['Data_Text']):
                            val = row['Data_Text']
                        elif pd.notna(row['Data_Double']):
                            val = row['Data_Double']
                        elif pd.notna(row['Data_Int32']):
                            val = row['Data_Int32']
                        elif pd.notna(row['Data_Boolean']):
                            val = bool(row['Data_Boolean'])
                        else:
                            continue
                            
                        record_model.metadata[friendly_name] = val
                
                record_key = record_model.metadata.get("Sample Name", f"Record_{record_id}")
                if record_key in records:
                    record_key = f"{record_key}_{record_id}"
                    
                records[record_key] = record_model

    except sqlite3.DatabaseError as e:
        file_metadata["extraction_error"] = f"Failed to open .zmes as SQLite DB: {str(e)}"
    except Exception as e:
        file_metadata["extraction_error"] = str(e)

    return ZmesDLSData(
        metadata=file_metadata,
        records=records
    )