import pandas as pd
import re
import io

def read_micromag_agm(filepath: str):
    metadata = {}
    segment_data_lines = []
    main_data_lines = []
    
    # These acts as switches so the code knows which table it is currently reading
    in_segment_table = False
    in_main_table = False
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        # --- Extract headers from the first two lines ---
        line1 = f.readline().strip()
        line2 = f.readline().strip()
        
        if "MicroMag" in line1:
            metadata["Instrument Model"] = line1.split("Data File")[0].strip()
            
            # Use regex to grab the version number inside the parentheses
            version_match = re.search(r'\(Series (.*?)\)', line1)
            if version_match:
                metadata["Data Format Version"] = version_match.group(1)
                
        # 2. Parse "Direct moment vs. field; Multiple segments"
        if ";" in line2:
            parts = line2.split(";")
            metadata["Measurement Type"] = parts[0].strip()
            metadata["Measurement Mode"] = parts[1].strip()


        for line in f:
            line_stripped = line.strip()
            
            # --- 1. MAIN DATA TABLE ---
            if in_main_table:
                # Stop if we hit the end-of-file text
                if line_stripped == "MicroMag 2900/3900 Data File ends":
                    break
                if line_stripped:
                    main_data_lines.append(line_stripped)
                continue
                
            # Trigger switch to turn ON the Main Data Table
            if "(Oe)" in line and "(emu)" in line and "(*)" in line:
                in_main_table = True
                continue
                
            # --- 2. SEGMENT TABLE ---
            if in_segment_table:
                # If we hit a blank line, the segment table is done. Turn the switch OFF.
                if not line_stripped:
                    in_segment_table = False
                    continue
                # If the line starts with a number, it's a data row for the segment table!
                if line_stripped[0].isdigit():
                    segment_data_lines.append(line_stripped)
                continue
                
            # Trigger switch to turn ON the Segment Table
            if line_stripped.startswith("Segment") and "Averaging" in line:
                in_segment_table = True
                continue
            
            # --- 3. METADATA ---
            # If we aren't inside either table, we must be looking at metadata
            if line_stripped:
                # Ignore the messy 3-line headers just above the segment table
                if line_stripped.startswith("Number") and "Time" in line_stripped:
                    continue
                if line_stripped.startswith("(s)"):
                    continue
                    
                # Split by 2 or more spaces
                parts = re.split(r'\s{2,}', line_stripped)
                if len(parts) == 2:
                    key, val = parts[0].strip(), parts[1].strip()
                    metadata[key] = val

    # Convert the collected text lines directly into pandas DataFrames
    
    # A. Build Segment DataFrame
    segment_df = pd.read_csv(
        io.StringIO("\n".join(segment_data_lines)), 
        header=None,
        names=[
            "Segment Number", "Averaging Time (s)", "Initial Field (Oe)", 
            "Field Increment (Oe)", "Final Field (Oe)", "Pause (s)", "Final Index"
        ]
    )
    
    # B. Build Main DataFrame
    main_df = pd.read_csv(
        io.StringIO("\n".join(main_data_lines)),
        header=None,
        names=["magnetic_field", "magnetic_moment", "normalized_moment"]
    )
    
    # Clean any potential bad strings that snuck in
    main_df['magnetic_field'] = pd.to_numeric(main_df['magnetic_field'], errors='coerce')
    main_df = main_df.dropna()
    
    # Return everything neatly packaged
    return {
        "metadata": metadata,
        "segments": segment_df,
        "magnetic_field": main_df['magnetic_field'].values,
        "magnetic_moment": main_df['magnetic_moment'].values
    }