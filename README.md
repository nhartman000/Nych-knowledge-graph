# knowledge-graph
A small graph database that connects NYCH word meanings to T.O.T.E. task loops. A sentence like "repair the failing unit test bug" is traced to a loop and its steps, checked by a gate (PASS / FAIL / INTERMEDIATE), given a permit if it passes, and recorded in a tamper-evident QSON audit file.

Organised with **Interpretable Context Methodology (ICM)**: https://arxiv.org/abs/2603.16021, https://github.com/RinDig/Interpretable-Context-Methodology. Work moves through the numbered folders in `stages/`. Each stage has instructions (`CONTEXT.md`), fixed rules (`references/`) and results (`output/`). A person approves each stage by editing `output/GATE.md`.

## Use
```
pip install -r requirements.txt
python stages/04-poc-run/poc.py "repair the failing unit test bug"     # needs stage 03 APPROVED
python stages/04-poc-run/poc.py --file sentences.txt                    # or: echo "..." | poc.py -
python stages/04-poc-run/poc.py verify stages/04-poc-run/output/traces/*.qson
python stages/04-poc-run/poc.py --force-demo "..."   # demo before approval -> stages/04-poc-run/demo_pre_approval/
```
`--rebuild` reloads the database; otherwise it persists between runs. Tests: `pip install -r requirements-dev.txt && pytest -q`.

- Schema (single source): `stages/02-schema/output/schema.cypher`
- Ontology map: `stages/03-ontology/output/ONTOLOGY.md`
- QSON hash chain: `stages/04-poc-run/qson_ledger.py`
