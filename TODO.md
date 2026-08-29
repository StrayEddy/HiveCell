<!-- BOARD
url: https://claude.ai/code/artifact/daa18251-ffd5-4b55-a1ee-751ffe7058e9
headline: On hold since 2026-08-05; the seal-drag bench test is the critical-path blocker gating #11, fault-injection sim is next desk work.
now:
- P0 #9 seal-drag bench test (~$200 sample, `docs/seal_drag_bench_test.md`, ADR-0011) — retires the master variable, gates #11
- P1 #3 randomized fault-injection on interlock timing (sim)
review:
-->

# HiveCell — TODO

**Status: on hold** since 2026-08-05. Narrative + priorities live in `docs/ROADMAP.md`; live discussion in GitHub Issues. This file is the actionable checklist the desktop board reads — keep the two in sync.

## Critical path (not desk work)
- [ ] #9 Seal-drag bench test (~$200 sample, `docs/seal_drag_bench_test.md`, ADR-0011) — retires the master variable, gates #11

## Next (desk work, medium)
- [ ] #3 Randomized fault-injection on interlock timing (sim)
- [ ] #4 Occupancy sensing tradeoff review — sensor table + fusion rationale (ADR-0012)
- [ ] #5 First-order reliability models — spring fatigue, cycle life, tolerance stack, ingress
- [ ] #6 Serviceability / manufacturability pass on the CAD

## Outreach (`docs/outreach.md`)
- [ ] Verify site is live and the demo video plays — https://strayeddy.github.io/HiveCell/
- [ ] First public post (Tue–Thu, 9–11am ET; stay around 3 h to answer comments)
- [ ] OSHWA certification — https://certification.oshwa.org (already qualifies: CERN-OHL-S); add UID + mark to README

## Hardware / context gated
- [ ] #7 SF1 real-sensing validation + ISO 13849 PL e dossier
- [ ] #8 SF2 drive force-limitability under a real jam (desk half done, ADR-0024)
- [ ] #11 SF4 return element + back-drive verification + actuator re-run
- [ ] #10 H4 siting sign-off vs local code + commissioning check

## Done
- [x] #1 TLA+ formal verification of interlock invariants, gated on push (found + fixed F-1, ADR-0022/0023)
- [x] #2 Safety requirements + traceability matrix + FTA (`docs/TRACEABILITY.md`)
- [x] #8 (desk half) SF2 force cap sourced from injury data, 120 N → 100 N (ADR-0024) — 2026-08-04
- [x] SF1 sensor suite: crown-mounted, CO2 dropped, load cells provisional (ADR-0025) — 2026-08-04
