"""Benchmark table-only lookup and live rules; optionally run the same LLM on both arms."""
import argparse
import json
import statistics
import subprocess
from pathlib import Path
from time import perf_counter

from table_216 import evaluate, read_table


def mn(id_, grade, thickness, answer, notes=(), *, killed=False, impact=False):
    question = (f"{grade}급, 두께 {thickness} mm, 킬드강 여부 {killed}, "
                f"충격시험 실시 여부 {impact}. 허용 가능한 Mn 최솟값(%)은?")
    return id_, question, dict(grade=grade, metric="mn_min", thickness_mm=thickness,
                               killed=killed, impact=impact), answer, list(notes)


def joint(id_, c, m, answer):
    question = f"A급 20 mm 강판, C {c}%, Mn {m}%. 표 2.1.6의 C·Mn 조건을 모두 충족하는가?"
    return id_, question, dict(grade="A", metric="a_plate_carbon_mn", thickness_mm="20",
                               carbon_pct=c, manganese_pct=m), answer, [4]


CASES = [
    mn("M01", "AH36", "12.49", 0.70, [7]),
    mn("M02", "AH36", "12.50", 0.70, [7]),
    mn("M03", "AH36", "12.51", 0.90),
    mn("M04", "FH36", "12.50", 0.90),
    mn("M05", "DH32", "10", 0.70, [7]),
    mn("M06", "B", "20", 0.60, [6], killed=True, impact=True),
    mn("M07", "B", "20", 0.80, killed=True),
    mn("M08", "B", "20", 0.80, impact=True),
    mn("M09", "B", "20", 0.80),
    joint("C01", "0.21", "1.20", False),
    joint("C02", "0.20", "1.20", True),
    joint("C03", "0.20", "1.21", False),
]


def call_llm(command, prompt):
    run = subprocess.run(command, input=prompt, capture_output=True, text=True,
                         encoding="utf-8", check=True, timeout=120)
    return run.stdout.strip()


def score(result, expected, notes):
    answer = result["answer"]
    value_match = (type(answer) is bool if type(expected) is bool
                   else type(answer) in {int, float}) and answer == expected
    return {"answer_correct": value_match,
            "strict_correct": value_match and sorted(result["notes"]) == notes}


def benchmark(command=None):
    start = perf_counter()
    raw, _, _ = read_table()
    extract_ms = (perf_counter() - start) * 1000
    parsed = None
    parse_ms = None
    if command:
        start = perf_counter()
        parsed = call_llm(command, "한국선급 문서의 표 2.1.6을 QA용 텍스트로 파싱하세요. "
                          "표의 병합 셀, 전체 비고와 번호를 보존하세요. 텍스트만 반환하세요.\n" + raw)
        if not parsed:
            raise ValueError("LLM parser returned an empty context")
        parse_ms = (perf_counter() - start) * 1000
    records = []
    for id_, question, query, expected, expected_notes in CASES:
        record = dict(id=id_, question=question, query=query,
                      expected={"answer": expected, "notes": expected_notes})
        for mode in ("table_only", "ontology"):
            start = perf_counter()
            output = evaluate(**query, apply_notes=mode == "ontology")
            record[mode] = {**output, **score(output, expected, expected_notes),
                            "ms": (perf_counter() - start) * 1000}
        if command:
            # Both arms retain the same LLM-parsed text. Only the latter adds solver output.
            for mode in ("llm", "llm_ontology"):
                context = parsed
                if mode == "llm_ontology":
                    context += "\n검증된 구조화 컨텍스트:\n" + record["ontology"]["context"]
                prompt = ("주어진 컨텍스트만 사용하세요. JSON만 출력하세요. "
                          '형식: {"answer": 숫자 또는 true/false, "notes": [실제 적용 비고 번호]}. '
                          "수치 질문에는 % 단위의 최솟값을 숫자로 반환하세요. "
                          "예외가 발동하지 않은 비고는 목록에서 제외하세요.\n"
                          f"질문: {question}\n컨텍스트:\n{context}")
                start = perf_counter()
                response = call_llm(command, prompt)
                try:
                    output = json.loads(response)
                    if not isinstance(output, dict) or not isinstance(output.get("notes"), list):
                        raise ValueError("Invalid response schema")
                    result = score(output, expected, expected_notes)
                except (KeyError, TypeError, ValueError):
                    result = {"answer_correct": False, "strict_correct": False}
                record[mode] = {"response": response, **result, "ms": (perf_counter() - start) * 1000}
        records.append(record)
    summary = {}
    modes = ["table_only", "ontology"] + (["llm", "llm_ontology"] if command else [])
    for mode in modes:
        summary[mode] = {
            "answer": sum(row[mode]["answer_correct"] for row in records),
            "strict": sum(row[mode]["strict_correct"] for row in records),
            "median_ms": round(statistics.median(row[mode]["ms"] for row in records), 3),
        }
    return {"n": len(records), "extract_ms": round(extract_ms, 3),
            "llm_parse_ms": round(parse_ms, 3) if parse_ms is not None else None,
            "llm_parsed_context": parsed, "summary": summary, "cases": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--llm-command", nargs=argparse.REMAINDER,
                        help="Executable and arguments; reads prompt on stdin, writes response on stdout")
    args = parser.parse_args()
    result = benchmark(args.llm_command)
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n": result["n"], "extract_ms": result["extract_ms"],
                      "summary": result["summary"]}, ensure_ascii=False, indent=2))
    if result["summary"]["ontology"]["strict"] != result["n"]:
        raise SystemExit("Ontology regression: at least one expected result differed")
