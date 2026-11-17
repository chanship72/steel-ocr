"""Page coordinates in PDF points, with origin at the top left."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PDF = ROOT.parent / "data" / "sample.pdf"
ROW_CENTERS = (228, 270, 312)
NOTE_CENTERS = (405, 445)
