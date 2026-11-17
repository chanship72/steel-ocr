---
tags:
  - steel-ocr
  - ontology
---

# 한국선급 OWL과 SMT-LIB 연결 예제

[[README|프로젝트 안내]] · [[data/2편_2025.pdf|로컬 규칙 PDF]]

한국선급 2025 제2편 인쇄면 90쪽, 표 2.1.88 비고 (2)를 사용한다. [한국선급 공식 PDF](https://www.krs.co.kr/KRRules/KRRules2025/data/data_part/korean/2%ED%8E%B8_2025.pdf)

- `ontology/ontology.ttl`은 OWL 클래스, 하위 클래스 공리, 표와 비고의 연결, 출처를 선언한다. 비고의 `kr:smtFunction` 주석이 실행할 SMT 함수 이름을 가리킨다.
- `ontology/rules.smt2`는 최소 인장강도에 따라 추가로 요구할 수 있는 상한의 최대값을 계산한다.
- `src/build_query.py`는 Turtle을 읽고, 이름이 있는 개체에 대해 클래스 포함·소속·객체 속성 사실을 불리언 제약으로 변환한다. Z3로 각주 유형이 도출되는지 확인하고, 질의 입력 및 산술 규칙을 결합해 `ontology/query.smt2`를 생성한다. 이 변환은 예제에서 사용하는 OWL 표현을 대상으로 한다.

프로젝트 루트 폴더에서 실행한다.

```powershell
python -m pip install -r requirements.txt
python src/build_query.py --minimum-mpa 600 --request-upper-limit
z3 -smt2 ontology/query.smt2
```

최소값 560 MPa에서는 상한을 최대 680 MPa로 요구할 수 있고, 600 MPa에서는 최대 750 MPa로 요구할 수 있다. `--request-upper-limit`을 생략하면 상한 적용 여부는 `false`이며 응답에 상한 수치가 없다. OCR 또는 MCP 코드에서는 `build_query(minimum, requested)`에 추출한 최소 인장강도와 질의 조건을 전달할 수 있다.
