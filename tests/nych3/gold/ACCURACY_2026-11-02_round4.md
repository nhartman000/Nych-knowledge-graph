# NYCH3 harvester accuracy — round 4 (2026-11-02)

Gold: `tests/nych3/gold/gold_v1.jsonl`, 300 sentences (75 per domain). **Agent-graded, pending human review.**
Before = round-3 code (commit 10663c8); after = round-4 code. Same gold, same harness (`nych3-eval`).

## Overall (P / R / F1)

| field | before | after |
|---|---|---|
| instruction_sentence | 0.958 / 0.962 / 0.960 | 0.962 / 0.957 / 0.960 |
| action | 0.935 / 0.682 / 0.789 | 0.938 / 0.679 / 0.788 |
| objects | 0.908 / 0.810 / 0.856 | 0.908 / 0.809 / 0.856 |
| locations | 0.544 / 0.784 / 0.643 | 0.549 / 0.775 / 0.642 |
| modality | 0.939 / 0.990 / 0.964 | 0.969 / 0.990 / 0.979 |
| exit_tier | 0.881 / 0.881 / 0.881 | 0.900 / 0.900 / 0.900 |
| exit | 0.881 / 0.881 / 0.881 | 0.900 / 0.900 / 0.900 |
| amount | 0.821 / 0.868 / 0.844 | 0.855 / 0.887 / 0.870 |
| actor | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 |

before: sentences correct/partial/wrong 143/135/22; loops 175/127/162

after: sentences correct/partial/wrong 146/132/22; loops 181/120/162

## Per domain (after, F1)

| domain | sentences c/p/w | instr | action | objects | locations | modality | exit_tier | amount |
|---|---|---|---|---|---|---|---|---|
| cooking | 27/48/0 | 1.000 | 0.812 | 0.767 | 0.634 | 0.980 | 0.887 | 0.588 |
| craft.knitting | 32/37/6 | 0.950 | 0.729 | 0.903 | 0.730 | 0.984 | 0.878 | 0.901 |
| craft.ropework | 48/22/5 | 0.932 | 0.844 | 0.853 | 0.526 | 0.978 | 0.935 | 1.000 |
| craft.woodworking | 39/25/11 | 0.947 | 0.794 | 0.954 | 0.615 | 0.972 | 0.923 | 1.000 |

## Error tally (after)

- missed_loop: 142
- locations_wrong: 73
- objects_wrong: 51
- missed_loop:bare_verb: 44
- exit_tier_wrong: 30
- spurious_loop: 20
- modality_wrong: 12
- gate_false_negative: 9
- amount_wrong: 9
- gate_false_positive: 8
- no_loop_matched: 5
