; KR 2025, Part 2, Table 2.1.6. Composition values are percent.
(define-fun note-six-applies ((killed Bool) (impact Bool)) Bool
  (and killed impact))
(define-fun note-seven-applies ((thickness Real)) Bool
  (<= thickness 12.5))
(define-fun note-six-min ((base Real) (killed Bool) (impact Bool)) Real
  (ite (note-six-applies killed impact) 0.60 base))
(define-fun note-seven-min ((base Real) (thickness Real)) Real
  (ite (note-seven-applies thickness) 0.70 base))
(define-fun joint-carbon-ok ((carbon Real) (manganese Real)) Bool
  (<= (+ (* 6 carbon) manganese) 2.40))
