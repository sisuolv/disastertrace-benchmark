# Cost-matched adaptive surface

Three tide replicas completed: two RTX 5090 and one H100, each with 384 cells and 500,000 targets per cell. `source_rr`, `source_hash`, and `active` all use two queries per target; `no_extra` uses one and `fixed` uses none. All methods share the same target/checkpoint denominator and forecast map.

Pooled active-minus-best-non-active Brier difference is **-0.01131132**; active wins 816/1152 cells. Active-minus-fixed is **-0.04394203**. The result is stable across the two RTX 5090 and H100 replicas. In this deliberately constructed process, the active arm uses the first signal to choose the follow-up whose reliability is high for that signal, so the result tests the intended causal mechanism rather than a free extra-query advantage.

The gain is conditional: at initial reliability `rho=0.9` the pooled active-minus-best-non-active difference becomes positive (`+0.014075`), while lower reliability strata favor active. A real run therefore needs a reliability estimate and a harm guard; the aggregate mean alone is not a safe deployment rule.

This is still synthetic evidence. It justifies a real development pilot with the same cost accounting and a strong fixed-follow-up control; it does not support a general novelty or weather claim.
