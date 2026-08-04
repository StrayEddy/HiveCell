# SF1 occupancy sensing — candidate parts & prices (issue #4, ADR-0012/ADR-0025)

**Goal:** put real part numbers and prices against the diverse channels ADR-0012
decided on, as flagged in [`SAFETY.md`](SAFETY.md)'s open items ("choose sensor part
numbers") and tracked as [#4](https://github.com/StrayEddy/HiveCell/issues/4). Also
covers the SF2 current-sense hardware, since it's the same "what do we actually buy"
question for issue #8's hardware half.

> **Superseded by ADR-0025.** Placement and suite composition were resolved after this
> survey was first written: **channel C (CO2) is dropped**, **channel D (load cells) is
> provisional** pending a piston-vibration bench test, and **placement is
> crown-mounted (fixed barrel ceiling) for A/B/E, floor-mounted for D, nothing on the
> piston**. Sections below are kept for the part/price research and marked accordingly
> rather than deleted.

> **This is a parts survey, not a certification decision.** Every module below is a
> commodity/prototyping-grade breakout — none of it is safety-rated out of the box.
> ADR-0012 calls for **PL e, Category 3-4** on the fused occupancy function, which
> means: a rated safety controller doing the voting (not the twin's ordinary MCU
> path), and a documented MTTFd/DC/CCF case per ISO 13849-1 for whatever channel
> hardware is finally chosen. The parts here are what you'd buy to **prototype and
> bench-validate each channel's physics** (does 60 GHz radar actually see a breathing
> rate through a blanket at HiveCell's range? does an 8x8 thermal array have enough
> resolution?) — that's the immediate need per #4 and ADR-0012's own accepted-cost
> list ("validate radar vital-sign range/reliability... on real hardware"). Whichever
> part wins the bench-off still has to clear a PL e dossier before it ships.

---

## 1. Channel A — mmWave/UWB vital-sign radar (primary) — crown-mounted

| Part | Vendor | Price (USD) | Grade | Notes |
|---|---|---:|---|---|
| **MR60BHA2** (XIAO 60 GHz mmWave breathing/heartbeat kit) | Seeed Studio | **$26.90** | Prototype | Onboard ESP32C6, outputs presence + breath rate + heart rate over UART already — fastest path to a bench demo. Predecessor MR60BHA1 is discontinued; use MR60BHA2. |
| **XM125** (Acconeer A121 Entry+ radar module) | Acconeer/Digi-Key | **$21.14** | Prototype | Pulsed coherent radar (not FMCW); ships with a presence detector, but vital-sign extraction is DIY (Acconeer's Exploration Tool has the primitives, not a turnkey heart-rate output). |
| **XE125** (Acconeer A121 eval board) | Acconeer/Digi-Key | **$121.09** | Prototype/dev | Full eval platform for the A121 IC above — more I/O and debug access than the bare module. |
| **IWR6843AOPEVM** (60 GHz AoP eval module) | TI | **$195.56** | Industrial dev | Raw ADC/point-cloud access, antenna-on-package. TI publishes a vital-signs reference design (people-counting + breathing/heart-rate) built on this family — the credible path if the Seeed kit's fixed firmware turns out too limited to validate through-bedding performance. |
| BGT60TR13C (bare IC) | Infineon/Digi-Key | **$19.72** | Component | For a from-scratch board once a reference design is chosen; not a plug-in module. |

**Recommendation for the bench pass:** start with the **MR60BHA2 ($27)** — cheapest,
fastest to a working demo, and its firmware already reports breath/heart rate, which is
the exact ADR-0012 open question ("validate radar vital-sign range/reliability through
bedding"). Keep the **IWR6843AOPEVM** in reserve if the fixed-firmware kit can't be
tuned/validated for HiveCell's geometry.

## 2. Channel B — Thermal IR array — crown-mounted, kept (ADR-0025)

No longer purely "supportive" now that C is dropped — see ADR-0025 point 4. It carries
more of the fused vote than ADR-0012 originally assumed.

| Part | Vendor | Price (USD) | Grade | Notes |
|---|---|---:|---|---|
| **AMG8833** (Panasonic Grid-EYE, 8×8) | Mouser | **~$17–40** (single-unit breakout ≈$35–40; ~$17 at MOQ 200) | Prototype | Coarse 8×8 grid — enough for "a warm body-shaped blob is/isn't in the bore." |
| **MLX90640** (Melexis, 32×24) | Mouser | **~$35–70** | Prototype | Higher resolution than AMG8833; only worth the premium if 8×8 proves too coarse to reject e.g. a warm pipe or heater vent as a false positive. |

**Recommendation:** AMG8833 first — cheaper, and the resolution bar is lower than 32×24.

## 3. Channel C — NDIR CO2 — **dropped, see ADR-0025**

~~Independent physics, penetration-independent (works under a blanket)~~ — dropped from
the suite. It was the one channel that categorically cannot take a solid flush window
(gas has to diffuse through something porous), forcing a more exposed, higher-
maintenance baffled vent than any other channel needs. Accepted cost: it was the only
channel that stayed elevated through a breath-hold/apnea event independent of RF
micro-motion; thermal partially, not fully, covers that gap (body heat outlasts a
breath-hold; CO2's chemical persistence doesn't have an exact substitute). Part research
kept below for reference only — not part of the current BOM.

| Part | Vendor | Price (USD) | Grade | Notes |
|---|---|---:|---|---|
| **SCD41** (Sensirion, photoacoustic NDIR, bare sensor) | Digi-Key | **$20.54** | Component | 10×10×6.5 mm, smallest footprint; needs your own board/I2C wiring. |
| **Adafruit SCD-41 breakout** (STEMMA QT) | Adafruit | **$49.95** | Prototype | Same sensor, ready-to-wire breakout. |
| **SCD30** (Sensirion, dual-channel NDIR) | Mouser/Digi-Key | **~$20–40** | Component/prototype | Older, larger, dual-channel-for-stability design. |

## 4. Channel D — Floor load cells + ballistocardiography — floor-mounted, provisional (ADR-0025)

**Provisional, not confirmed.** Stays in the suite only if a bench test (not yet run)
shows piston-drive vibration, coupled through the shared fixed-floor structure, doesn't
swamp the BCG micro-motion signal — or that drive-telemetry reference-subtraction
recovers it. The mass-presence half of this channel (unaffected by vibration, since it's
a static reading, not a micro-motion one) is not in question; the BCG half is. If the
bench test fails, this whole section drops and the confirmed suite is radar + thermal
only.

| Part | Vendor | Price (USD) | Grade | Notes |
|---|---|---:|---|---|
| **50 kg half-bridge load cell + HX711 ADC kit** (4-pack + amplifier) | Amazon/eBay | **~$16–20** for the whole kit | Prototype/hobby | 24-bit HX711 ADC is the standard hobby path to BCG-scale resolution (micro weight-shifts from pulse/breathing) — this is what most published bed/floor-BCG research setups (e.g. the PMC longitudinal-BCG study surveyed here) actually build on. |
| **Single-point load cell, 100 kg or 200 kg capacity** | ATO.com | **$96.56** each | Industrial | For the "static mass = something present" half — 100 kg is plenty of headroom per corner for an adult occupant's weight split across 4 cells; the HX711 kit's 50 kg hobby cells are undersized once you're load-bearing rather than just sensing micro-motion. |

**Recommendation:** this channel actually needs **two different grades doing two
different jobs** — the coarse "is there load-bearing mass at all" reading wants the
industrial 100 kg single-point cells (4 per cell, corners, **~$390** for the set) sized
for real body weight; the BCG micro-motion signal on top of that can run off the same
cells through a 24-bit HX711 front end (~$5–10 per channel) rather than needing separate
hardware — no need to buy the 50 kg hobby load cells too.

## 5. Channel E (optional) — mouth-plane presence during motion — mouth-frame-mounted, not crown

ADR-0012 flags this as optional and names it for reach-in detection during a sweep, not
steady-state occupancy — which changes the sourcing question: this one plausibly needs
to *be* a safety function on its own (SF-adjacent), not just a bench-validation input.

| Part | Vendor | Price (USD) | Grade | Notes |
|---|---|---:|---|---|
| **VL53L5CX breakout** (8×8-zone ToF) | SparkFun/Pololu | **~$32.50** | Prototype | Fine for bench characterization of the reach-in geometry/timing, but it is a consumer ToF chip — not safety-rated, no certified stop path. |
| **Omron F3SG-4RA / F3SJ safety light curtain**, PL e / Cat 4 / SIL3 | Omron/Newark | **from ~€529 (~$570+)**, scales with protected height | Safety-certified | If E gets promoted from optional to required (DECISIONS.md flags this for the H4 sitting-height mouth siting), this is the class of part that actually satisfies a PL e dossier — a certified light curtain, not a hobby ToF board doing the same job in software. |

**Recommendation:** VL53L5CX now for bench geometry/timing studies; budget for a
certified light curtain (~$600+) only if/when E is promoted to required per the H4
follow-up in DECISIONS.md.

## 6. SF2-adjacent — force/current sensing on the real drive (issue #8 hardware half)

Not an ADR-0012 channel, but the same "what part number" question applies to the other
open hardware item (#8: can the real drive hold the 100 N cap under a jam). Force
limiting on a chain/actuator drive is normally done by motor current sensing, not a
separate mechanical force sensor:

| Part | Vendor | Price (USD) | Grade | Notes |
|---|---|---:|---|---|
| **ACS712** (Hall-effect current sensor, ±30 A) | various/eBay | **~$1.50–8** per breakout | Prototype | Cheapest way to bench-correlate motor current to output force on a test rig; used in exactly this role in hobby linear-actuator projects. |
| **ACS37800** (Allegro, isolated AC/DC power-monitor IC) | Pololu/Mouser/Digi-Key | price not confirmed — check distributor directly | Component/industrial | Reinforced isolation, ±30 A bidirectional, I2C/SPI output — the credible upgrade from ACS712 if the final drive electronics need a certifiable current-sense path rather than a hobby breakout. |

## 7. Rough bench-validation BOM (one cell, prototype-grade, per-unit qty 1)

| Channel | Part | Price |
|---|---|---:|
| A — radar | MR60BHA2 | $26.90 |
| B — thermal | AMG8833 | ~$38 |
| ~~C — CO2~~ | *dropped, ADR-0025* | — |
| D — load/BCG (provisional) | 4× ATO 100 kg single-point cell + HX711 front end | ~$396 + ~$10 |
| E — reach-in (optional) | VL53L5CX breakout | $32.50 |
| SF2 current sense | ACS712 breakout | ~$5 |
| **Total (D pending bench test)** | | **≈ $510/cell** (≈$440 without optional E) |
| **Total if D fails its bench test** | | **≈ $105/cell** (radar + thermal + SF2 only, ≈$70 without E) |

This is a single bench-validation set per channel, not a BOM for a certified unit —
final parts (especially D and E) will very likely change once the PL e dossier and real
mounting/EMC constraints (radar-in-metal-bore, per ADR-0012's accepted costs) are
worked out.

## 8. What this doesn't answer

- No pricing here reflects volume/production cost — these are single-unit
  prototyping prices only.
- None of these parts carry a safety certification; the PL e dossier (category,
  MTTFd, DC, CCF per ISO 13849-1) still has to be built once parts are chosen, per
  ADR-0012's follow-ups and `SAFETY.md`'s open items.
- Radar-through-metal-bore EMC and mounting/field-of-view (no dead zones) are
  unverified for all radar candidates above — bench characterization, not a catalog
  lookup, will decide this.
- Channel E's fate (optional vs. required) is upstream of its part choice — see
  ADR-0013 / the H4 follow-up in `DECISIONS.md`.

## Sources

- [Seeed Studio — MR60BHA2](https://www.seeedstudio.com/MR60BHA2-60GHz-mmWave-Sensor-Breathing-and-Heartbeat-Module-p-5945.html)
- [Acconeer A121 / XM125 / XE125](https://www.waveshare.com/a121-range-sensor.htm)
- [TI IWR6843AOPEVM](https://www.ti.com/tool/IWR6843AOPEVM)
- [Infineon BGT60TR13C — Digi-Key](https://www.digikey.com/en/products/detail/infineon-technologies/BGT60TR13CE6327XUMA1/13282953)
- [Panasonic AMG8833 — Mouser](https://www.mouser.com/ProductDetail/Panasonic/AMG8833)
- [Melexis MLX90640 — Mouser](https://www.mouser.com/new/melexis/melexis-mlx90640-fir-sensor)
- [Sensirion SCD41 — Digi-Key](https://www.digikey.com/en/products/detail/sensirion-ag/SCD41-D-R2/13684004)
- [Adafruit SCD-41](https://www.adafruit.com/product/5190)
- [Sensirion SCD30](https://sensirion.com/products/catalog/SCD30)
- [ATO.com — single point load cell](https://www.ato.com/single-point-load-cell-300g-to-500kg)
- [VL53L5CX — SparkFun](https://www.sparkfun.com/sparkfun-qwiic-tof-imager-vl53l5cx.html)
- [Omron F3SG-4RA safety light curtain — Newark](https://www.newark.com/omron-industrial-automation/f3sg4ra120014/safety-light-curtain-cat4-1-2m/dp/74Y6328)
- [Allegro ACS37800 — Pololu](https://www.pololu.com/category/343/acs37800-isolated-power-monitor-carriers)
- [ACS712 current-sense-for-actuator-limits example](https://www.instructables.com/Using-an-Using-an-ACS712-and-Arduino-to-detect-act/)
