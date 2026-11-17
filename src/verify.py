"""End-to-end comparison against requirements transcribed from the sample PDF."""
from dataclasses import replace

from ocr import read_pdf
from qa import infer, lookup

CASES = [
    ("DEMO-355", "40", (470, 630), []),
    ("DEMO-355", "40.01", (450, 630), ["A"]),
    ("DEMO-355", "60", (450, 630), ["A"]),
    ("DEMO-355", "60.01", (450, 610), ["A", "B"]),
    ("DEMO-420", "60", (520, 680), []),
    ("DEMO-420", "65", (520, 610), ["B"]),
    ("DEMO-500", "65", (580, 750), []),
]

def pair(result):
    return result["min_mpa"], result["max_mpa"]


def main():
    baseline_correct = ontology_correct = 0
    for grade, thickness, expected, markers in CASES:
        answer = lookup(grade, thickness)
        inferred = answer["ontology"]
        assert inferred["status"] == "ok", answer
        baseline = pair(answer["ocr_only"])
        actual = pair(inferred)
        baseline_correct += baseline == expected
        ontology_correct += actual == expected
        assert actual == expected, answer
        assert [note["marker"] for note in inferred["applied_footnotes"]] == markers
        print(f"{grade:8} {thickness:>5} mm  {baseline} -> {actual}  notes={markers}")

    assert lookup("UNKNOWN", "65")["status"] == "unknown_grade"
    assert lookup("DEMO-355", "0")["status"] == "invalid_thickness"
    rows, notes = read_pdf()
    # Synthetic collision: two active notes assign different values to the same endpoint.
    conflict = {**notes, "B": replace(notes["B"], endpoint="minimum")}
    assert infer(rows["DEMO-355"], conflict, "65")["status"] == "conflict"
    print(f"Exact range matches: OCR {baseline_correct}/{len(CASES)}, "
          f"ontology {ontology_correct}/{len(CASES)}")


if __name__ == "__main__":
    main()
