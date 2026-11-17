; KR 2025 Part 2, Table 2.1.88, note (2).
; This is the largest upper limit that may be requested, in MPa.
(define-fun max-requestable-upper-mpa ((minimum Int)) Int
  (+ minimum (ite (< minimum 600) 120 150)))
