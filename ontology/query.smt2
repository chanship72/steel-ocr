; urn:kr:rules:2025:part2:table_2_1_88 / urn:kr:rules:2025:part2:table_2_1_88_note_2
(declare-const BindingTable__table_2_1_88 Bool)
(declare-const BindingTable__table_2_1_88_note_2 Bool)
(declare-const Footnote__table_2_1_88 Bool)
(declare-const Footnote__table_2_1_88_note_2 Bool)
(declare-const OptionalUpperLimitNote__table_2_1_88 Bool)
(declare-const OptionalUpperLimitNote__table_2_1_88_note_2 Bool)
(assert (=> OptionalUpperLimitNote__table_2_1_88 Footnote__table_2_1_88))
(assert (=> OptionalUpperLimitNote__table_2_1_88_note_2 Footnote__table_2_1_88_note_2))
(assert BindingTable__table_2_1_88)
(assert OptionalUpperLimitNote__table_2_1_88_note_2)
(declare-const hasFootnote__table_2_1_88__table_2_1_88_note_2 Bool)
(assert hasFootnote__table_2_1_88__table_2_1_88_note_2)
; KR 2025 Part 2, Table 2.1.88, note (2).
; This is the largest upper limit that may be requested, in MPa.
(define-fun max-requestable-upper-mpa ((minimum Int)) Int
  (+ minimum (ite (< minimum 600) 120 150)))
(define-fun minimum_mpa () Int 600)
(define-fun upper_limit_requested () Bool true)
(define-fun upper_limit_applies () Bool (and upper_limit_requested (and Footnote__table_2_1_88_note_2 hasFootnote__table_2_1_88__table_2_1_88_note_2)))
(define-fun max_requestable_upper_mpa () Int (max-requestable-upper-mpa minimum_mpa))
(check-sat)
(get-value (minimum_mpa upper_limit_applies max_requestable_upper_mpa))
