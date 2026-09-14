# Complete captured-model rescoring capsule

Run `python3 -B verify.py --capsule . --result ../model-rescoring.json` with Python 3.10 or newer. No third-party package, model, API, or network is needed. Use a fresh result location: the rescoring output is never overwritten.

All 212 original Qwen3-235B tasks, visible inputs, references, fitted banks, requests, replies, publication receipts, and the original frozen scorer are included. Both invalid replies remain. The verifier checks byte bindings, reruns the full scorer, independently recomputes Brier statistics and same-member temperature event fractions, and compares every score row with the original.

This rebuilds the captured-model scores, not the model generations. Original token qualification is included as a receipt; tokenizer/weights are excluded. Full source archives, training-data reconstruction, active-session journals, API experiments, and physical measurement truth are outside this capsule. The raw METAR text is reparsed by the frozen provider parser, not a second independent physical decoder. The Python audit hook prevents accidental network and original-workspace reads in this verifier; it is not an adversarial sandbox.
