# Outreach checklist & post drafts

A living checklist for getting HiveCell in front of the people who can help —
builders, safety engineers, and open-hardware folks. The goal is **hands and
scrutiny**, not money: the next real step (the seal-drag bench test) is cheap, so
what the project needs is contributors and eyes.

Everything links to the live site: **https://strayeddy.github.io/HiveCell/**

---

## 0. Before posting (once)

- [ ] Site is live and the demo video plays — https://strayeddy.github.io/HiveCell/
- [ ] Repo About/website field points at the site (done)
- [ ] `CONTRIBUTING.md` lists the seal-drag test as the top ask (done)
- [ ] Pick a time: post on **Tue–Thu, ~9–11am US Eastern** for the widest awake audience
- [ ] Be around for the first ~3 hours to answer comments — early engagement decides reach

---

## 1. OSHWA certification (free, ~10 min)

Gets HiveCell into the Open Source Hardware directory and lets it carry the OSHW mark.

- [ ] Go to **https://certification.oshwa.org** → "Get Started" / "Certify"
- [ ] You already qualify: hardware is **CERN-OHL-S**, docs are public
- [ ] Register HiveCell; you'll receive a UID (e.g. `US000123`)
- [ ] Add the UID + OSHW mark to the README and (optionally) the site footer
- [ ] Directory listing itself is a passive, permanent source of discovery

---

## 2. Post drafts (paste-ready)

Tone: honest, safety-first, not hypey. Lead with the interesting hard problem
(safe motion around a sleeping, vulnerable person), and end with a concrete ask.

### Hacker News — "Show HN"
**Title:** `Show HN: HiveCell – open-source, safe-by-design public sleeping infrastructure`

**Body:**
> HiveCell is a powered sleeping cell recessed in a wall that retracts flush to
> self-clean between uses. The hard part isn't the mechanism — it's safety: it moves
> a steel piston through a space a sleeping, possibly intoxicated or unwell person
> occupies and may not be able to self-rescue from. So the whole design is PREVENT
> (never move while occupied) → REACT (stop & reverse on contact) → fail safe;
> "push the occupant out" is not a mode it can enter.
>
> It's **design + simulation only, uncertified** — no built hardware yet. What exists
> is worked fully in the open: an ADR decision log, an FMEA, a Godot digital twin that
> runs the real interlock (with headless safety self-tests that gate every commit), a
> diverse-redundant occupancy-sensor model (radar vitals + thermal + CO₂ + load/BCG)
> targeting ISO 13849 PL e, and first-order FEM/actuator sizing.
>
> I'm a solo maintainer. I'd love (a) scrutiny from anyone in machine safety /
> ISO 13849, and (b) help with the single biggest unknown — a ~$200 seal-drag bench
> measurement that unblocks the whole force chain (procedure's in the repo).
>
> Site + demo video: https://strayeddy.github.io/HiveCell/
> Code: https://github.com/StrayEddy/HiveCell

### Reddit — r/opensourcehardware, r/engineering, r/functionalsafety
**Title:** `HiveCell: an open-source, safe-by-design public sleeping cell (design + sim, looking for safety review)`

**Body:** (same hook as above, trimmed) then:
> The #1 thing I need help with is a **~$200 seal-drag bench measurement** — it's the
> master unknown that sizes the actuator, the return spring, and the drive choice. Full
> procedure is in the repo. Also very keen on safety-case review. Not selling anything;
> it's CERN-OHL-S / CC-BY / Apache-2.0.
>
> Site + demo: https://strayeddy.github.io/HiveCell/

*(Read each subreddit's self-promo rules first; frame as "sharing a project + asking
for review", engage in comments.)*

### Hackaday.io — create a project
- Title: **HiveCell — safe-by-design public sleeping infrastructure**
- Short description: *A powered sleeping cell that retracts into a wall to self-clean —
  engineered to fail safe around a sleeping, vulnerable occupant. Open source.*
- Use the poster image as the project logo; add a build log entry linking the repo +
  the seal-drag test as the open call for help.
- Hackaday's audience is exactly the builder/maker pool that could run the bench test.

### One-line version (for Mastodon / LinkedIn / comments)
> Open-source, safe-by-design public sleeping infrastructure — a powered cell that fails
> safe around a sleeping occupant. Design + simulation, uncertified, looking for safety
> review and a $200 bench test. https://strayeddy.github.io/HiveCell/

---

## 3. After posting

- [ ] Answer every substantive comment (especially safety critiques — those are gold)
- [ ] Log any credible safety concern as a GitHub issue and reference it
- [ ] If someone offers to run the seal-drag test, point them at
      `docs/seal_drag_bench_test.md` and offer to help interpret the result
- [ ] Note what resonated; reuse it in the next post / a grant application
