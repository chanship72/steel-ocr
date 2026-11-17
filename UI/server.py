"""Serve the Table 2.1.6 comparison on loopback."""
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

UI = Path(__file__).resolve().parent
ROOT = UI.parent
sys.path.insert(0, str(ROOT / "src"))

from benchmark_216 import CASES
from table_216 import evaluate

ASSETS = {
    "/": (UI / "index.html", "text/html; charset=utf-8"),
    "/app.js": (UI / "app.js", "text/javascript; charset=utf-8"),
    "/style.css": (UI / "style.css", "text/css; charset=utf-8"),
    "/table.png": (ROOT / "report" / "table_2.1.6.png", "image/png"),
}
CASES_BY_ID = {case[0]: case for case in CASES}


def recorded_results():
    path = ROOT / "data" / "table_216_llm.json"
    if not path.is_file():
        return {}
    result = json.loads(path.read_text(encoding="utf-8-sig"))
    return {case["id"]: case for case in result["cases"]}


class Handler(BaseHTTPRequestHandler):
    def send_body(self, status, mime, body):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_body(status, "application/json; charset=utf-8", body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ASSETS:
            file, mime = ASSETS[path]
            self.send_body(200, mime, file.read_bytes())
        elif path == "/api/cases":
            self.send_json([{"id": case[0], "question": case[1]} for case in CASES])
        elif path.startswith("/api/cases/"):
            case = CASES_BY_ID.get(path.removeprefix("/api/cases/"))
            if case is None:
                self.send_json({"error": "등록된 질의를 찾을 수 없습니다."}, 404)
                return
            id_, question, query, answer, notes = case
            try:
                baseline = evaluate(**query, apply_notes=False)
                inferred = evaluate(**query, trace=True)
                recorded = recorded_results().get(id_, {})
                if recorded.get("query") != query:
                    recorded = {}
                self.send_json({
                    "id": id_, "question": question, "query": query,
                    "expected": {"answer": answer, "notes": notes},
                    "baseline": baseline, "inferred": inferred,
                    "recorded": {key: recorded.get(key) for key in ("llm", "llm_ontology")},
                })
            except (OSError, ValueError, RuntimeError) as error:
                self.send_json({"error": str(error)}, 500)
        else:
            self.send_json({"error": "경로를 찾을 수 없습니다."}, 404)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with HTTPServer(("127.0.0.1", args.port), Handler) as server:
        print(f"http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()
