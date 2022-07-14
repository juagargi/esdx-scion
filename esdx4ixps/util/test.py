from pathlib import Path

def test_data(file: Path=None) -> Path:
    p = Path(__file__).parent.parent.parent.joinpath("test_data")
    return p.joinpath(file) if file is not None else p
