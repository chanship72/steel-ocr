const $ = (id) => document.getElementById(id);
const selector = $("case");
let currentRequest = 0;

async function get(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error ?? response.statusText);
  return data;
}

function display(value) {
  return typeof value === "boolean" ? (value ? "조건 충족" : "조건 위반") : value.toFixed(2) + "%";
}

function render(data) {
  $("question").textContent = data.question;
  for (const mode of ["baseline", "inferred"]) {
    $(mode).textContent = display(data[mode].answer);
    $(mode + "-context").textContent = data[mode].context;
  }
  const notes = data.expected.notes.join(", ") || "없음";
  $("expected").textContent = "검증 정답 · " + display(data.expected.answer) + " · 적용 비고 " + notes;
  for (const mode of ["llm", "llm_ontology"]) {
    const item = data.recorded[mode];
    $(mode).textContent = item ? item.response : "저장된 응답 없음";
  }
  const trace = data.inferred.trace;
  const rules = trace.rules.map((rule) =>
    "비고 (" + rule.note + ") · " + rule.class + " → " + rule.function +
    "\n" + rule.condition + " = " + rule.applied
  ).join("\n");
  const steps = [
    ["evaluate(**query, trace=True)", JSON.stringify(data.query, null, 2)],
    ["read_table() → markers(cell)", trace.cell + "\n셀에 연결된 비고: " + (data.inferred.linked_notes.join(", ") || "없음")],
    ["ontology() → OWL 번호·클래스·함수 매핑", rules || "이 셀에 연결된 실행 규칙이 없습니다."],
    ["solver.from_string(smtlib) → solver.check()", "(assert (= answer " + trace.expression + "))\ncheck() → " + trace.status],
    ["solver.model().eval(answer)", JSON.stringify(trace.bindings, null, 2)]
  ];
  $("steps").replaceChildren(...steps.map(([name, body]) => {
    const li = document.createElement("li");
    const title = document.createElement("code");
    title.textContent = name;
    const detail = document.createElement("pre");
    detail.textContent = body;
    li.append(title, detail);
    return li;
  }));
  $("smt").textContent = trace.smtlib;
  $("command").textContent =
    "$query = @'\n" + JSON.stringify(data.query, null, 2) +
    "\n'@\n$query | .\\.venv\\Scripts\\python.exe src\\table_216.py --trace";
  $("results").hidden = false;
}

async function run() {
  const request = ++currentRequest;
  $("status").textContent = "PDF와 Z3 결과를 확인하는 중…";
  $("question").textContent = "";
  $("results").hidden = true;
  try {
    const data = await get("/api/cases/" + encodeURIComponent(selector.value));
    if (request === currentRequest) {
      render(data);
      $("status").textContent = "";
    }
  } catch (error) {
    if (request === currentRequest) $("status").textContent = error.message;
  }
}

async function start() {
  try {
    for (const item of await get("/api/cases")) {
      selector.add(new Option(item.id + " · " + item.question, item.id));
    }
    selector.value = "M02";
    selector.disabled = false;
    selector.addEventListener("change", run);
    await run();
  } catch (error) {
    $("status").textContent = error.message;
  }
}

start();
