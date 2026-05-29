# readers-ientrance
Parses raw, proprietary instrument data files into clean, strictly typed Python objects (Pandas/NumPy) for FAIR-compliant databases like NOMAD.

# Installation
```sh
pip install git+https://github.com/glaidedata/readers-ientrance.git
```

# Quick Start
```py
from readers_ientrance import read_arc
# Load the file
data = read_arc("path/to/arc_data.txt")

# Access extracted data instantly
print(data.metadata["Test Cell Type"])  # Dictionary of header/footer metadata
print(data.sample_temperature)          # NumPy array of the data column
print(data.data)                        # Full Pandas DataFrame
```
