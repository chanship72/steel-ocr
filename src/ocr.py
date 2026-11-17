"""OCR and strict parsing for the sample's one-page layout."""
import re
from dataclasses import dataclass
from functools import lru_cache

import pymupdf
import numpy as np
from rapidocr_onnxruntime import RapidOCR

from layout import NOTE_CENTERS, PDF, ROW_CENTERS

NOTE = re.compile(
    r"Note\s+([A-Z])\s*:\s*For\s+t\s*>\s*(\d+(?:\.\d+)?)\s*mm,\s*"
    r"replace\s+(minimum|maximum)\s+with\s+(\d+)\s*MPa\.?",
    re.IGNORECASE,
)
COLUMNS = ((59, 174), (209, 260), (328, 379), (450, 515))


@dataclass(frozen=True)
class Evidence:
    text: str
    confidence: float
    bbox_pt: tuple[int, int, int, int]
    page: int = 1


@dataclass(frozen=True)
class Row:
    grade: str
    lower: int
    upper: int
    markers: tuple[str, ...]
    cells: tuple[Evidence, ...]


@dataclass(frozen=True)
class Footnote:
    marker: str
    threshold: str
    endpoint: str
    value: int
    evidence: Evidence


@lru_cache(maxsize=1)
def read_pdf():
    engine = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
    with pymupdf.open(PDF) as document:
        page = document[0]

        def read(left, right, y):
            box = (left, y - 15, right, y + 15)
            pixels = page.get_pixmap(clip=pymupdf.Rect(box), dpi=216, alpha=False)
            rgb = np.frombuffer(pixels.samples, dtype=np.uint8)
            rgb = rgb.reshape(pixels.height, pixels.width, 3)
            ys, xs = np.nonzero(rgb.max(axis=2) < 155)
            if not xs.size:
                raise ValueError(f"No dark text in OCR region on page 1: {box}")
            ink = rgb[ys.min():ys.max() + 1, xs.min():xs.max() + 1, ::-1]
            crop = np.pad(ink, ((8, 8), (8, 8), (0, 0)), constant_values=255)
            result, _ = engine(crop, use_det=False,
                               use_cls=False, use_rec=True)
            if not result or not result[0][0].strip() or result[0][1] < 0.65:
                raise ValueError(f"Unreadable OCR region on page 1: {box}, {result!r}")
            value, confidence = result[0]
            return Evidence(value.strip(), float(confidence), box)

        rows = {}
        for y in ROW_CENTERS:
            cells = tuple(read(left, right, y) for left, right in COLUMNS)
            grade, lower, upper, markers = (cell.text.upper() for cell in cells)
            markers = re.sub(r"\s+", "", markers)
            if (not re.fullmatch(r"DEMO-\d+", grade) or grade in rows
                    or not re.fullmatch(r"\d+", lower)
                    or not re.fullmatch(r"\d+", upper)
                    or not re.fullmatch(r"NONE|[A-Z](?:,[A-Z])*", markers)
                    or not 0 < int(lower) <= int(upper)):
                raise ValueError(f"Invalid OCR table row: {cells!r}")
            rows[grade] = Row(grade, int(lower), int(upper),
                              () if markers == "NONE" else tuple(markers.split(",")), cells)

        notes = {}
        for y in NOTE_CENTERS:
            evidence = read(49, 560, y)
            match = NOTE.fullmatch(evidence.text)
            if not match:
                raise ValueError(f"Unsupported footnote syntax: {evidence.text!r}")
            marker, threshold, endpoint, value = match.groups()
            marker = marker.upper()
            if marker in notes or int(value) <= 0:
                raise ValueError(f"Invalid or duplicate footnote: {evidence.text!r}")
            notes[marker] = Footnote(marker, threshold, endpoint.lower(), int(value), evidence)

    missing = {marker for row in rows.values() for marker in row.markers} - notes.keys()
    if missing:
        raise ValueError(f"Missing footnote definitions: {sorted(missing)}")
    return rows, notes
