# Gate — 04-poc-run
status: PENDING
reviewer:
notes: Blocked until stage 03 GATE.md is APPROVED. The runner refuses to run without it (use --force-demo for a labelled pre-approval demo).
Checklist:
- [ ] stage 03 approved
- [ ] `python stages/04-poc-run/poc.py --file <sentences>` run; outputs in output/
- [ ] `python stages/04-poc-run/poc.py verify stages/04-poc-run/output/traces/*.qson` all OK
- [ ] human sign-off
