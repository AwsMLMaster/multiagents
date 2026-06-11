# Innovation Proposal: Grid Radar — The Power Network as a Self-Sensing Fabric

**A fusion of electromagnetics/physics, power-systems engineering, RF signal
processing, and data science / machine learning.**

Date: 2026-06-11

---

## TL;DR

The electrical grid is the largest machine ever built — millions of kilometers
of conductor reaching nearly every structure on Earth. We use it to move power.
We almost never use it to **sense itself.**

A conductor carrying power is also a transmission line in the RF sense: inject a
low-energy, wide-band coded signal onto an energized line and the **reflections**
that come back encode everything the line is touching — a developing fault, a
loose connector heating up, a tree branch leaning into a span, ice loading,
conductor sag, even an illegal tap. This is **reflectometry**, and it is mature
in narrow niches (aircraft wiring, lab cable testing). It has **never been turned
into a continuous, grid-wide, ML-interpreted "radar."**

The proposed innovation: **treat the power grid as a single distributed radar
array.** Every substation and smart device becomes a transceiver that constantly
pings its lines with coded signals, and a data-science layer fuses the millions
of returning echoes into a live map of grid health — locating and *predicting*
faults **before** they cause an outage or a fire.

The killer application writes itself: **wildfire prevention.** Utility equipment
faults — a slapping conductor, a failing splice, vegetation contact — ignite some
of the most catastrophic and expensive wildfires on record, exposing utilities to
tens of billions in liability. A grid that can hear a fault forming, minutes to
weeks early, and locate it to the span, is worth an enormous amount.

Every component exists today. Nobody has assembled them into this category. The
barrier is integration and adoption, **not new physics.**

---

## The unmet need

- **Utilities are largely blind between sensors.** They know voltage and current
  at substations and at scattered meters, but the *physical state of the wire
  itself* — the splice that's corroding, the branch that's encroaching, the
  insulator that's cracking — is invisible until it fails. Inspection is manual,
  periodic, and expensive (helicopters, trucks, line crews).
- **Failures are catastrophic and lagging.** The first signal of many faults is
  the outage — or the ignition. Wildfire liability has bankrupted major utilities.
- **Vegetation management is a multi-billion-dollar guess.** Utilities trim on
  fixed schedules across entire territories because they can't see *which*
  specific spans are actually at risk *right now.*
- **Grid-edge complexity is exploding.** Rooftop solar, EV chargers, and
  batteries inject faults and harmonics from millions of new points. The
  monitoring model built for one-way power flow is obsolete.

The thesis: **the wire is already a sensor — we just throw the signal away.**
The reflected energy on every line carries a continuous diagnosis of its own
condition. We have never systematically listened.

---

## The science it stands on (all published / deployed, not invented here)

| Established capability | Domain |
|---|---|
| Spread-spectrum / time-domain reflectometry (SSTDR) locates faults and impedance changes on **energized, live** conductors | RF / electromagnetics |
| Power-line communication (PLC) already injects and recovers high-frequency signals on live power lines at scale | Power electronics / comms |
| Partial-discharge and high-frequency signatures predict insulation and connector failure | High-voltage engineering |
| Distributed sensing + ML can localize events across large networks by fusing many weak, noisy channels | Data science / signal processing |
| Smart meters, reclosers, and inverters are already programmable transceivers sitting on the grid edge | Grid hardware (installed base) |

Every row is real and shipped **separately.** The innovation is the **integration
into a continuous, network-wide, learning radar** — and the reframing of fault
*detection* into fault *prediction.*

---

## What is actually new here

The novelty is not a new sensor or a new wave. It is a **systems reframing**:

> Stop treating the grid as something we monitor from a few fixed points, and
> start treating the conductor network itself as a single, coherent, always-on
> radar array whose echoes a learning system interprets in real time.

Specifically novel claims:
1. **Network-wide coherence.** Reflectometry today is point-to-point on one
   cable. Fusing reflections from *thousands of transceivers across a meshed
   network* — using the redundancy to triangulate and de-noise — is a different,
   unbuilt thing. It is the difference between one sonar ping and a phased array.
2. **Prediction, not detection.** ML on the *time-evolution* of echo signatures
   turns "a fault happened at km 3.2" into "this splice's signature is drifting
   the way splices do three weeks before they fail."
3. **A new device category — "self-sensing grid."** One physical layer serving
   predictive maintenance, wildfire risk, vegetation targeting, theft detection,
   and even environmental sensing (lines respond to wind, ice, temperature).

---

## Feasibility: three tiers, honestly graded

### Tier 1 — Buildable today, no new science (MVP)
Single-feeder pilot: install SSTDR transceivers at a substation and a handful of
reclosers on one distribution feeder. Continuously profile the feeder; flag and
locate impedance anomalies. Validate against known/seeded faults and inspection
records.

- Risk: **Low.** All hardware is off-the-shelf; SSTDR-on-live-lines is proven.
  The output — "here is a developing fault at this location" — is immediately
  useful and easy to validate against ground truth.

### Tier 2 — Plausible with focused R&D (2–4 yrs)
Scale to a meshed network with many transceivers; build the **coherent fusion +
ML** layer that triangulates events and learns failure-precursor signatures from
labeled outage/inspection history. Deliver a live risk map.

- Risk: **Medium.** Main unknowns: signal-to-noise on long, branchy, noisy
  distribution networks, and getting enough *labeled* failure data to train
  reliable precursor models. Both are addressable with pilots and transfer
  learning from accelerated-aging lab data.

### Tier 3 — Ambitious frontier (research bet)
A continental "grid radar" standard: every smart inverter, meter, and recloser
participates as a coherent node, yielding a real-time national map of grid health
**and** an incidental environmental sensor network (ice storms, wind loading,
even seismic coupling through structures).

- Risk: **High but high-reward.** This is mostly a standardization, security, and
  data-governance challenge — not a physics one.

---

## Why it's feasible *and* why it isn't already done

It isn't done because it requires **fusing communities that don't share a
language**: RF/reflectometry specialists (who think about single cables), power
engineers (who think in 50/60 Hz and protection relays, not GHz echoes), ML
people (who rarely touch high-voltage hardware), and utility operators (who buy
proven boxes, not research). The barrier is **organizational and conceptual**, and
adoption-cycle conservatism in a safety-critical industry — **not a missing
breakthrough.** That is the most attractive kind of barrier.

---

## Honest open questions (the things that could kill it)

1. **Signal-to-noise on real distribution networks.** Branches, taps,
   transformers, and switching noise scatter and attenuate the coded signal. The
   open question is how far down a messy feeder useful echoes survive. Tier-1
   pilots answer this directly.
2. **Labeled failure data is scarce.** Predicting failures needs examples of
   failures. Accelerated-aging labs and historical outage records can bootstrap
   it, but cold-start accuracy is a real risk.
3. **Localization ambiguity in meshed topologies.** Multiple reflection paths can
   alias. This is exactly why network-wide coherence (many transceivers) matters —
   redundancy resolves ambiguity, but proving it at scale is Tier-2 work.
4. **Cybersecurity.** Anything that injects signals onto the grid and exposes a
   live health map is a security surface that must be designed for from day one.

---

## Suggested first experiment (cheapest decisive test)

Take one distribution feeder in a high-fire-risk area. Instrument it with SSTDR
transceivers at the substation and 3–5 reclosers. Run continuously for one season
alongside the utility's normal inspections. Two readouts:
**(A)** Can the system *locate* seeded/known impedance faults to within a span?
**(B)** Looking back after any real fault or near-miss, did the echo signature
**drift detectably beforehand** (retrospective precursor analysis)?
If A succeeds and B shows even a modest predictive lead time, the entire thesis is
validated for the cost of a single-feeder instrumentation pilot — and the network-
coherence and wildfire-risk products are de-risked to build next.

---

## Value to the customer (since that's the right next question)

- **Utilities (primary buyer):** Slashed wildfire-ignition liability — the single
  biggest financial exposure many utilities face. Vegetation management spent
  where it's actually needed instead of blanket trimming. Fewer unplanned outages
  (better reliability metrics, which regulators penalize). Inspection shifted from
  expensive periodic patrols to condition-based, targeted dispatch.
- **Regulators / public:** Fewer catastrophic fires and blackouts; faster
  restoration because faults are pre-located.
- **Ratepayers:** Lower long-run cost of grid maintenance and avoided
  catastrophe-recovery costs that ultimately land on bills.
- **Insurers / reinsurers:** A quantifiable, continuously-updated grid-risk signal
  to price wildfire and outage risk — and to reward utilities that deploy it.
- **Grid-edge operators (data centers, large C&I):** Early warning on their own
  feeders, protecting sensitive loads.

**The single sharpest value statement:** *the grid can already hear itself
failing — this listens, locates the failure to the span, and warns before the
outage or the fire, using hardware that is mostly already in the ground.*

---

## How this complements the first proposal

The glymphatic-delivery concept and Grid Radar share the same DNA, which is why I
think both are worth backing:

- Both are **integration plays built from existing, shipped parts** — the risk is
  clinical/operational, never "can the physics work."
- Both **slave a system to a signal we currently discard** (the brain's clearance
  cycle; the wire's reflected echoes).
- Both have a **cheap, decisive go/no-go experiment** that retires the core risk
  before any large commitment.
- Both define a **new category** rather than a single product.

That pattern — *fuse mature parts across siloed communities, listen to a signal
everyone throws away, and prove it with one cheap experiment* — is the repeatable
engine behind both ideas, and the lens I'd use to find the next one.
