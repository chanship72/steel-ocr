"""Ground the supported OWL axioms over named individuals and build a Z3 query."""
import argparse
import re
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS
import z3

ONTOLOGY_DIR = Path(__file__).resolve().parent.parent / "ontology"
KR = Namespace("urn:kr:rules:2025:part2:")
TABLE = KR.table_2_1_88
NOTE = KR.table_2_1_88_note_2


def symbol(uri):
    if not isinstance(uri, URIRef) or not str(uri).startswith(str(KR)):
        raise ValueError(f"Expected a named KR resource: {uri}")
    name = str(uri)[len(str(KR)):]
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) or "__" in name:
        raise ValueError(f"Invalid KR resource identifier: {uri}")
    return name


def owl_constraints(graph):
    classes = set(graph.subjects(RDF.type, OWL.Class))
    individuals = set(graph.subjects(RDF.type, OWL.NamedIndividual))
    properties = set(graph.subjects(RDF.type, OWL.ObjectProperty))
    facts = set()
    facts.update((c, i) for i in individuals for c in graph.objects(i, RDF.type) if c in classes)
    links = set()
    inclusions = set(graph.subject_objects(RDFS.subClassOf))
    for child, parent in inclusions:
        if child not in classes or parent not in classes:
            raise ValueError("Only declared named classes are supported in SubClassOf")
    for prop in properties:
        for source, target in graph.subject_objects(prop):
            if source not in individuals or target not in individuals:
                raise ValueError("Object property assertions require named individuals")
            links.add((prop, source, target))

    declarations = {(c, i) for c in classes for i in individuals}
    # Each supported ground atom can be true or false unless the axioms constrain it.
    lines = [f"(declare-const {symbol(c)}__{symbol(i)} Bool)"
             for c, i in sorted(declarations)]
    lines.extend(f"(assert (=> {symbol(c)}__{symbol(i)} {symbol(p)}__{symbol(i)}))"
                 for c, p in sorted(inclusions) for i in sorted(individuals))
    lines.extend(f"(assert {symbol(c)}__{symbol(i)})" for c, i in sorted(facts))
    for prop, source, target in sorted(links):
        name = f"{symbol(prop)}__{symbol(source)}__{symbol(target)}"
        lines.extend([f"(declare-const {name} Bool)", f"(assert {name})"])
    return lines


def build_query(minimum, requested):
    if type(minimum) is not int or minimum <= 0:
        raise ValueError("Minimum tensile strength must be a positive integer in MPa")
    graph = Graph().parse(ONTOLOGY_DIR / "ontology.ttl", format="turtle")
    if (TABLE, KR.hasFootnote, NOTE) not in graph:
        raise ValueError("Table-to-footnote link is unconfirmed")
    rule = str(graph.value(NOTE, KR.smtFunction, any=False))
    if not re.fullmatch(r"[a-z][a-z0-9-]*", rule):
        raise ValueError("Expected one SMT function identifier for the footnote")
    applies = f"(and Footnote__{symbol(NOTE)} hasFootnote__{symbol(TABLE)}__{symbol(NOTE)})"
    axioms = owl_constraints(graph)
    # Check entailment so the query cannot assume a missing classification.
    solver = z3.Solver()
    solver.from_string("\n".join([*axioms, f"(assert (not {applies}))"]))
    if solver.check() != z3.unsat:
        raise ValueError("The ontology does not establish that the table uses this footnote")
    lines = [
        f"; {TABLE} / {NOTE}",
        *axioms,
        (ONTOLOGY_DIR / "rules.smt2").read_text(encoding="utf-8").rstrip(),
        f"(define-fun minimum_mpa () Int {minimum})",
        f"(define-fun upper_limit_requested () Bool {str(requested).lower()})",
        f"(define-fun upper_limit_applies () Bool (and upper_limit_requested {applies}))",
        "(check-sat)",
    ]
    # The input owns the optional requirement; a missing maximum is not encoded as zero.
    if requested:
        lines.insert(-1, f"(define-fun max_requestable_upper_mpa () Int ({rule} minimum_mpa))")
        lines.append("(get-value (minimum_mpa upper_limit_applies max_requestable_upper_mpa))")
    else:
        lines.append("(get-value (minimum_mpa upper_limit_applies))")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum-mpa", required=True, type=int)
    parser.add_argument("--request-upper-limit", action="store_true")
    parser.add_argument("--output", type=Path, default=ONTOLOGY_DIR / "query.smt2")
    args = parser.parse_args()
    args.output.write_text(build_query(args.minimum_mpa, args.request_upper_limit), encoding="utf-8")
