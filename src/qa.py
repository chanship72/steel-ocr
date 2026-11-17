import argparse
import json
import re
from dataclasses import asdict
from decimal import Decimal

import z3

from layout import ROOT
from ocr import read_pdf

ONTOLOGY = ROOT.parent / "ontology" / "ontology.smt2"


def bounds(lower, upper):
    return {"min_mpa": lower, "max_mpa": upper}


def infer(row, notes, thickness):
    program = [
        ONTOLOGY.read_text(encoding="utf-8"),
        "(declare-const lower Int)",
        "(declare-const upper Int)",
    ]
    active = {}
    by_endpoint = {"minimum": [], "maximum": []}
    for index, note in enumerate(notes.values()):
        name = f"active_{index}"
        footnote = f"footnote_{index}"
        active[note.marker] = name
        by_endpoint[note.endpoint].append(name)
        linked = str(note.marker in row.markers).lower()
        min_note = str(note.endpoint == "minimum").lower()
        max_note = str(note.endpoint == "maximum").lower()
        program += [
            f"(declare-const {name} Bool)",
            f"(declare-const {footnote} Bool)",
            f"(assert (dl-note-axioms {footnote} {min_note} {max_note}))",
            f"(assert (= {name} (applies {footnote} {linked} {thickness} {note.threshold})))",
            f"(assert (note-merge {name} {min_note} {max_note} {note.value} lower upper))",
        ]

    has_min, has_max = (
        f"(or {' '.join(symbols)})" if len(symbols) > 1
        else next(iter(symbols), "false")
        for symbols in by_endpoint.values()
    )
    program.append(f"(assert (table-merge {has_min} {has_max} {row.lower} {row.upper} lower upper))")
    ctx = z3.Context()
    solver = z3.Solver(ctx=ctx)
    solver.set(timeout=2000)
    solver.from_string("\n".join(program))
    status = solver.check()
    if status == z3.unsat:
        return {"status": "conflict"}
    if status != z3.sat:
        return {"status": "solver_unknown", "reason": solver.reason_unknown()}

    model = solver.model()
    lower, upper = z3.Int("lower", ctx), z3.Int("upper", ctx)
    lo, hi = model.eval(lower), model.eval(upper)
    applied = [asdict(notes[marker]) for marker, symbol in active.items()
               if z3.is_true(model.eval(z3.Bool(symbol, ctx)))]
    solver.add(z3.Or(lower != lo, upper != hi))
    uniqueness = solver.check()
    if uniqueness == z3.sat:
        return {"status": "ambiguous"}
    if uniqueness != z3.unsat:
        return {"status": "solver_unknown", "reason": solver.reason_unknown()}
    return {"status": "ok", **bounds(lo.as_long(), hi.as_long()), "applied_footnotes": applied}


def lookup(grade: str, thickness_mm: str) -> dict:
    """Return tensile requirements for a grade and an exact decimal thickness in mm."""
    grade = grade.strip().upper()
    thickness = thickness_mm.strip()
    if not re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,9})?", thickness) or Decimal(thickness) <= 0:
        return {"status": "invalid_thickness", "expected": "positive decimal string in mm"}

    rows, notes = read_pdf()
    if grade not in rows:
        return {"status": "unknown_grade", "available_grades": list(rows)}
    row = rows[grade]
    thickness = format(Decimal(thickness), "f")
    return {
        "document": "DEMO-STEEL-01",
        "table": 1,
        "grade": grade,
        "thickness_mm": thickness,
        "ocr_only": bounds(row.lower, row.upper),
        "ontology": infer(row, notes, thickness),
        "row_evidence": [asdict(cell) for cell in row.cells],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("grade")
    parser.add_argument("thickness_mm")
    args = parser.parse_args()
    print(json.dumps(lookup(args.grade, args.thickness_mm), indent=2))
