# knowledge-graph
A small graph database that connects NYCH word meanings to T.O.T.E. task loops, so a sentence like "repair the failing unit test bug" can be traced to the exact loop, steps, and a pass/fail check, with an audit trail.

Organised with **Interpretable Context Methodology (ICM)** — https://arxiv.org/abs/2603.16021, https://github.com/RinDig/Interpretable-Context-Methodology. Work flows through numbered folders in `stages/`; each has instructions (`CONTEXT.md`), stable rules (`references/`) and results (`output/`). A person approves each stage by editing `output/GATE.md`.

Quick start: see `setup/questionnaire.md`, then `python stages/04-poc-run/poc.py`. Ontology map: `stages/03-ontology/output/ONTOLOGY.md`.
