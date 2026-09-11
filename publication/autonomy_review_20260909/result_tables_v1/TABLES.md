# Verified P11-P14 tables

- Primary accuracy uses all planned slots; returned-only accuracy is supplementary.
- All methods receive identical cumulative source evidence plus their own declared carrier.
- Different conditions generate separate histories; there is no shared-prefix causal estimate.
- Later conditions have less collection time before the shared deadline; deadline censoring is not a pure prompt-role effect.
- Six development storms and repeat0 support descriptive results only.
- These three protocol cells are not a complete role-by-whitespace factorial.
- H100 hours are generation-job allocation time, including loading; preflights are separate.
- Grouped CSV values are counts; missing error-category cells mean zero occurrences.

| Phase | Model | Condition | Returned / planned | Strictly correct | Strict % | H100 allocation h |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| p11 | qwen3 | system_any_spacing | 2412/2412 | 1000 | 41.4594 | 5.2233 |
| p11 | deepseek_r1 | system_any_spacing | 1604/2412 | 3 | 0.1244 | 2.8317 |
| p12 | qwen3 | system_default_spacing | 2412/2412 | 1060 | 43.9469 | 5.0731 |
| p12 | deepseek_r1 | system_default_spacing | 1994/2412 | 9 | 0.3731 | 2.6797 |
| p13 | deepseek_r1 | user_default_spacing | 2064/2412 | 6 | 0.2488 | 2.8650 |
| p14 | qwen3 | user_default_spacing | 1628/2412 | 952 | 39.4693 | 3.2606 |

## Method counts

| Phase | Model | Method | Returned / planned | Shape valid | Strictly correct | Whole targets / 144 |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| p11 | qwen3 | snapshot | 804/804 | 804 | 356 | 4/144 |
| p11 | qwen3 | structured_state | 804/804 | 803 | 345 | 22/144 |
| p11 | qwen3 | answer_history | 804/804 | 804 | 299 | 15/144 |
| p11 | deepseek_r1 | snapshot | 538/804 | 524 | 1 | 0/144 |
| p11 | deepseek_r1 | structured_state | 530/804 | 491 | 1 | 0/144 |
| p11 | deepseek_r1 | answer_history | 536/804 | 499 | 1 | 0/144 |
| p12 | qwen3 | snapshot | 804/804 | 804 | 369 | 6/144 |
| p12 | qwen3 | structured_state | 804/804 | 804 | 369 | 23/144 |
| p12 | qwen3 | answer_history | 804/804 | 804 | 322 | 13/144 |
| p12 | deepseek_r1 | snapshot | 667/804 | 664 | 3 | 0/144 |
| p12 | deepseek_r1 | structured_state | 661/804 | 650 | 1 | 0/144 |
| p12 | deepseek_r1 | answer_history | 666/804 | 629 | 5 | 0/144 |
| p13 | deepseek_r1 | snapshot | 686/804 | 682 | 0 | 0/144 |
| p13 | deepseek_r1 | structured_state | 686/804 | 676 | 3 | 0/144 |
| p13 | deepseek_r1 | answer_history | 692/804 | 653 | 3 | 0/144 |
| p14 | qwen3 | snapshot | 543/804 | 543 | 315 | 8/144 |
| p14 | qwen3 | structured_state | 540/804 | 540 | 340 | 10/144 |
| p14 | qwen3 | answer_history | 545/804 | 545 | 297 | 10/144 |
