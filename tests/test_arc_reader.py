import numpy as np
from readers_ientrance.arc_reader import read_arc


def test_read_arc_valid_file(tmp_path):
    """Test that the reader correctly extracts metadata and arrays from a standard ARC file."""
    # 1. Create a temporary mock ARC file
    mock_file = tmp_path / "test_arc.txt"
    mock_content = (
        "Current Time;2026-01-23 16:24:38\n"
        "Sample Name;Al2O3\n"
        "Sample Mass;9.9\n"
        "Test Cell Type;SS316L\n"
        "\n"
        "Serial Number;Current Time;Sample Temperature;Pressure;Power1\n"
        "0;16:24:39;32.95;0.10;0.00\n"
        "1;16:24:40;33.00;0.11;0.01\n"
    )
    mock_file.write_text(mock_content)

    # 2. Run the reader
    result = read_arc(str(mock_file))

    # 3. Assert Metadata Extraction
    assert result.metadata.get("Current Time") == "2026-01-23 16:24:38"
    assert result.metadata.get("Sample Name") == "Al2O3"
    assert result.metadata.get("Sample Mass") == "9.9"
    assert result.metadata.get("Test Cell Type") == "SS316L"

    # 4. Assert Array Extraction
    assert result.serial_number is not None
    assert np.array_equal(result.serial_number, [0, 1])

    assert result.current_time is not None
    assert np.array_equal(result.current_time, ["16:24:39", "16:24:40"])

    assert result.sample_temperature is not None
    assert np.array_equal(result.sample_temperature, [32.95, 33.00])

    assert result.pressure is not None
    assert np.array_equal(result.pressure, [0.10, 0.11])

    # 5. Verify unprovided columns remain None safely
    assert result.power2 is None


def test_read_arc_empty_file(tmp_path):
    """Test that the reader does not crash when given an empty file."""
    mock_file = tmp_path / "empty_arc.txt"
    mock_file.write_text("")

    result = read_arc(str(mock_file))

    assert result.metadata == {}
    assert result.serial_number is None
    assert result.sample_temperature is None


def test_read_arc_utf16_fallback(tmp_path):
    """Test that the reader successfully triggers its UTF-16 fallback logic."""
    mock_file = tmp_path / "utf16_arc.txt"
    mock_content = (
        "Sample Name;Al2O3\n"
        "Serial Number;Current Time;Sample Temperature\n"
        "0;16:24:39;32.95\n"
    )

    # Write the file as raw UTF-16 bytes
    mock_file.write_bytes(mock_content.encode("utf-16"))

    result = read_arc(str(mock_file))

    assert result.metadata.get("Sample Name") == "Al2O3"
    assert result.sample_temperature is not None
    assert result.sample_temperature[0] == 32.95  # noqa: PLR2004