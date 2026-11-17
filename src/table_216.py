"""Read the real KR PDF and evaluate Table 2.1.6 notes (4), (6), (7)."""
import argparse
import json
import re
import sys
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import pymupdf
import z3
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "data" / "2편_2025.pdf"
PAGE = 17
KR = Namespace("urn:kr:2025:table-2.1.6:")
GLYPHS = str.maketrans({"\ue0f8": "t", "\ue042": "%"})
NOTES = {"joint-carbon-ok", "note-six-min", "note-seven-min"}


def clean(value):
    return " ".join(value.translate(GLYPHS).split())


def markers(value):
    return {int(n) for n in re.findall(r"\((\d+)\)", value)}


def number(value):
    value = str(value)
    if not re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,8})?", value):
        raise ValueError(f"Expected a nonnegative decimal: {value}")
    return format(Decimal(value), "f")


@lru_cache(maxsize=2)
def read_table(pdf=PDF):
    with pymupdf.open(pdf) as doc:
        page = doc[PAGE - 1]
        raw = page.get_text().replace("\ue00c\ue0f2", "Mn").translate(GLYPHS)
        if "2.1.6" not in raw or "(비고)" not in raw:
            raise ValueError("Expected KR 2025 Table 2.1.6 on PDF page 17")
        table = next(t for t in page.find_tables().tables if t.col_count == 18)
        extracted = table.extract()
        columns = [sum(table.rows[1].cells[i][::2]) / 2 for i in (4, 6)]
        rows = {}
        grade = None
        for index, row in enumerate(extracted[2:-1], start=2):
            if row[1]:
                grade = re.sub(r"\s+", "", row[1])
            anchor = next(cell for cell in table.rows[index].cells if cell is not None)
            y = (anchor[1] + table.rows[index].bbox[3]) / 2
            # A merged cell covers every row whose sample point falls inside its box.
            fields = []
            for x in columns:
                box = next(b for b in table.cells if b[0] < x < b[2] and b[1] < y < b[3])
                fields.append(clean(page.get_textbox(box)))
            if grade in {"A", "B"} or re.fullmatch(r"[ADEF]H(?:32|36|40)", grade or ""):
                rows[grade] = fields
        notes = dict((int(k), clean(v)) for k, v in
                     re.findall(r"^\((\d+)\)\s*(.*?)(?=^\(\d+\)|\Z)",
                                raw.split("(비고)", 1)[1], re.M | re.S))
        return raw, rows, notes


@lru_cache(maxsize=1)
def ontology():
    graph = Graph().parse(ROOT / "ontology" / "table_216.ttl", format="turtle")
    rules = {}
    for subject, label in graph.subject_objects(KR.predicate):
        kind = next(c for c in graph.objects(subject, RDF.type)
                    if (c, RDFS.subClassOf, KR.Footnote) in graph)
        name = str(label)
        if name not in NOTES:
            raise ValueError(f"Unsupported predicate: {name}")
        rules[int(graph.value(subject, KR.number, any=False))] = (name, str(kind))
    return rules, (ROOT / "ontology" / "table_216.smt2").read_text(encoding="utf-8")


def evaluate(grade, metric, thickness_mm, killed=None, impact=None,
             carbon_pct=None, manganese_pct=None, *, apply_notes=True, trace=False):
    grade = re.sub(r"\s+", "", grade.upper())
    thickness = number(thickness_mm)
    if not 0 < Decimal(thickness) <= 100:
        raise ValueError("Supported thickness is 0 < t <= 100 mm")
    _, rows, notes = read_table()
    if metric == "mn_min" and grade == "B" and apply_notes:
        if type(killed) is not bool or type(impact) is not bool:
            raise ValueError("B-grade Mn requires both killed and impact conditions")
    if grade not in rows:
        raise ValueError(f"Unsupported grade: {grade}")
    carbon, mn = rows[grade]
    cell = mn if metric == "mn_min" else carbon
    linked = markers(cell)
    rules, definitions = ontology() if apply_notes else ({}, "")
    checks = {}
    if metric == "mn_min" and grade != "A":
        base = re.match(r"[0-9.]+", mn).group()
        expr = base
        for n in sorted(linked & rules.keys()):
            fn, _ = rules[n]
            if n not in notes:
                raise ValueError(f"Footnote ({n}) missing from PDF")
            if fn == "note-seven-min":
                checks[n] = f"(note-seven-applies {thickness})"
                expr = f"({fn} {expr} {thickness})"
            if fn == "note-six-min":
                flags = f"{str(killed).lower()} {str(impact).lower()}"
                checks[n] = f"(note-six-applies {flags})"
                expr = f"({fn} {expr} {flags})"
    elif metric == "a_plate_carbon_mn" and grade == "A":
        c, m = number(carbon_pct), number(manganese_pct)
        cap = re.match(r"[0-9.]+", carbon).group()
        ratio = re.match(r"[0-9.]+", mn).group()
        expr = f"(and (<= {c} {cap}) (>= {m} (* {ratio} {c})))"
        if 4 in markers(mn) & linked & rules.keys():
            fn, _ = rules[4]
            if 4 not in notes:
                raise ValueError("Footnote (4) missing from PDF")
            expr = f"(and {expr} ({fn} {c} {m}))"
            checks[4] = "true"
    else:
        raise ValueError("Unsupported grade and metric combination")

    ctx = z3.Context()
    solver = z3.Solver(ctx=ctx)
    sort = "Real" if metric == "mn_min" else "Bool"
    program = [definitions, f"(declare-const answer {sort})",
               f"(assert (= answer {expr}))"]
    for n, condition in checks.items():
        program.extend([f"(declare-const applied_{n} Bool)",
                        f"(assert (= applied_{n} {condition}))"])
    smtlib = "\n".join(program)
    solver.from_string(smtlib)
    status = solver.check()
    if status != z3.sat:
        raise RuntimeError("Z3 did not return a model")
    key = z3.Real("answer", ctx) if sort == "Real" else z3.Bool("answer", ctx)
    model = solver.model()
    value = model.eval(key)
    evidence = [n for n in checks if z3.is_true(model.eval(z3.Bool(f"applied_{n}", ctx)))]
    answer = float(value.as_fraction()) if sort == "Real" else z3.is_true(value)
    raw_cell = f"C {carbon}; Mn {mn}" if metric == "a_plate_carbon_mn" else mn
    result = {
        "answer": answer, "notes": evidence, "table": "2.1.6", "pdf_page": PAGE,
        "cell": raw_cell, "linked_notes": sorted(linked),
        "context": (f"표 2.1.6, PDF 17쪽. {grade}, 두께 {thickness} mm. "
                    f"표 본문: {raw_cell}. "
                    f"{'유효 Mn 하한(%)' if sort == 'Real' else 'C·Mn 조건 충족 여부'}: {answer}. "
                    f"적용 비고: {evidence}. " + " ".join(f"({n}) {notes[n]}" for n in evidence)),
    }

    if trace:
        result["trace"] = {
            "cell": raw_cell,
            "rules": [{
                "note": n, "class": rules[n][1].rsplit(":", 1)[-1],
                "function": rules[n][0], "condition": checks[n],
                "applied": n in evidence,
            } for n in checks],
            "expression": expr,
            "smtlib": smtlib,
            "status": str(status),
            "bindings": {
                "answer": str(value),
                **{f"applied_{n}": str(n in evidence).lower() for n in checks},
            },
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="JSON object; defaults to stdin")
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()
    query = json.loads(args.query if args.query is not None else sys.stdin.read())
    print(json.dumps(evaluate(**query, trace=args.trace), ensure_ascii=False, indent=2))
