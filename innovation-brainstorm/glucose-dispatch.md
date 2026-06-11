# Innovation Proposal: Glucose Dispatch — Closed-Loop *Drug-Free* Metabolic Demand-Response

**A fusion of consumer continuous glucose monitoring, exercise physiology
(insulin-independent muscle glucose uptake), and control theory / demand-response
engineering.**

Date: 2026-06-11

> This is a full-depth proposal, written to the standard of the glymphatic, Grid
> Radar, and ReCharge write-ups — and with an explicit **prior-art / novelty
> boundary** section, because the previous shortlist included an idea (LLM +
> formal verification) that already existed. The claim here is deliberately
> narrow and checked: see §"The precise novelty boundary."

---

## TL;DR

Tens of millions of people now wear **continuous glucose monitors (CGMs)** without
having diabetes — the metabolic-wellness boom (over-the-counter sensors launched
2024). But every one of these products is an **open-loop dashboard**: it *shows*
you a glucose spike and *nags* you, after the fact. It does not *do* anything in
the moment.

Meanwhile, exercise physiology has known for decades that **muscle contraction
clears glucose from the blood through a pathway that does not require insulin**
(contraction triggers GLUT4 transporters to the muscle-cell surface directly).
Even trivial contractions — calf raises, "soleus pushups," a two-minute walk —
measurably blunt a post-meal glucose rise.

The innovation fuses these with a third idea borrowed from the power grid:
**demand-response dispatch.** The grid handles a demand spike by dispatching a
flexible resource the instant it's detected. **Glucose Dispatch** does the same to
a glucose spike: the moment your CGM detects a post-meal rise beginning, the system
**dispatches a precisely-dosed, minimal muscle-contraction protocol** — timed,
quantified, and closed-loop — to flatten the curve using your own skeletal muscle
as the actuator. **Drug-free, free to run, and using your body's own
insulin-independent glucose sink on demand.**

The reframe: stop treating skeletal muscle as a thing you "should exercise" and
start treating it as a **dispatchable glucose-disposal resource** slaved to a
real-time metabolic signal. Every component exists and ships. The closed loop —
*contraction as the dispatched actuator* — has not been built.

---

## The unmet need

- **Postprandial spikes harm even non-diabetics.** Large, repeated post-meal
  glucose excursions are linked to metabolic decline, energy crashes, and
  cardiovascular risk *before* anyone meets a diabetes threshold. The CGM-wellness
  market exists precisely because people now *see* these spikes — and feel
  helpless to stop them in real time.
- **Today's tools only observe.** OTC CGM apps score your day, show graphs, and
  send "you spiked" notifications. The user is left to vaguely "eat better" or
  "move more" — open-loop, delayed, unquantified guidance.
- **The pharmacological answer is expensive and rationed.** GLP-1 drugs work but
  are costly, supply-constrained, have side effects, and aren't appropriate for
  the merely-metabolically-curious. There is a **free, drug-free physiological
  lever** sitting unused: the insulin-independent contraction pathway.

The thesis: **the most powerful real-time glucose-lowering tool most people own is
their own calf muscle — and no product dispatches it.** We have the sensor and we
have the actuator; nobody has closed the loop between them.

---

## The science it stands on (established, not invented here)

| Established finding | Domain |
|---|---|
| Muscle contraction translocates GLUT4 and clears blood glucose **independently of insulin** | Exercise physiology |
| Skeletal-muscle glucose uptake can rise many-fold during contraction; even low-intensity activity blunts postprandial excursions | Exercise physiology |
| Tiny, sustained calf contractions (the "soleus" mechanism) raise glucose disposal disproportionately to their effort | Recent muscle-metabolism work |
| CGMs give continuous, real-time interstitial glucose and are now **OTC consumer devices** | Sensor / wearable industry |
| Demand-response control — detect a spike, dispatch a flexible resource in real time — is a mature engineering discipline | Control theory / power systems |

Every row is real and shipping **separately.** The innovation is the **closed
control loop**: CGM as the sensor, a quantified micro-contraction protocol as the
*dispatched actuator*, and a controller deciding *when and how much* to dispatch.

---

## What is actually new here

> Reframe skeletal muscle from "exercise you ought to do" into a **dispatchable,
> insulin-independent glucose sink**, and close a real-time control loop that fires
> it the instant a CGM detects a spike beginning — drug-free metabolic
> demand-response.

Specifically novel claims:
1. **Contraction is the actuator, not a disturbance.** Existing closed loops
   (artificial pancreas) dispatch *insulin* and treat exercise as a *disturbance to
   compensate for.* This **inverts** that: the dispatched resource *is* the
   contraction, and no drug is involved.
2. **Dispatch, not nagging.** A real-time controller computes *a specific dose*
   (e.g., "90 seconds of soleus contractions now") sized to the detected rise —
   quantified and closed-loop, versus today's vague after-the-fact alerts.
3. **A new category — "metabolic demand-response."** A drug-free, sensor-driven
   platform that treats the body's own physiology as a fleet of dispatchable
   resources timed to a live signal.

---

## The precise novelty boundary (what already exists, and why this is still unbuilt)

Being explicit here, because rigor on this is the whole point:

- **Artificial-pancreas / closed-loop *insulin* systems** exist and even include
  exercise-aware algorithms. **But they dispatch insulin**; exercise is modeled as
  a *disturbance* that perturbs the insulin controller — the opposite of using
  contraction *as* the controlled actuator. Glucose Dispatch is **drug-free** and
  for the **non-diabetic** wellness population.
- **"Exercise snacks," post-meal walks, and soleus-pushup research** establish that
  the physiology works — but as *general advice / study protocols*, not as a
  **CGM-triggered, real-time, closed-loop dispatch product.**
- **IP exists in the neighborhood** (e.g., patents on interactive exercise therapy
  and CGM-informed activity). So this is **not a green field** — a real build must
  navigate prior art and likely differentiate on the *specific controller* (spike-
  onset detection → dosed contraction protocol) and the consumer closed-loop UX.

Net: the *physiology* is proven, the *sensor* is a commodity, and the *control
concept* is standard — but the **assembled closed loop with contraction as the
dispatched actuator, for non-diabetic real-time spike flattening,** is not a
product. That is the narrow, defensible 1+1.

---

## Feasibility: three tiers, honestly graded

### Tier 1 — Buildable today, no new science (MVP)
A software layer on top of an existing OTC CGM: detect the **onset slope** of a
post-meal rise, and immediately prompt a **specific, quantified micro-contraction
protocol** (e.g., timed soleus contractions or a brisk 2-minute walk), then measure
the resulting area-under-the-curve reduction and learn each user's response.

- Risk: **Low.** Pure software + behavioral protocol over a shipping sensor. The
  value (flatten *this* spike, right now, drug-free) is immediate and measurable
  per user against their own untreated spikes.

### Tier 2 — Plausible with focused R&D (1–3 yrs)
Add a **wearable contraction sensor/actuator** (an instrumented band or a
calf/EMS device) to (a) *confirm* the dispatched contraction actually happened and
to what degree, and optionally (b) *assist* it via neuromuscular stimulation —
turning "please do calf raises" into a measured, even partly-automated, dispatch.
Personalize the controller to each user's glucose-vs-contraction response curve.

- Risk: **Medium.** Main unknowns below; the actuator hardware and EMS are mature,
  but proving consistent, comfortable, sufficient glucose disposal is the work.

### Tier 3 — Ambitious frontier (research bet)
**Closed-loop neuromuscular dispatch**: a low-profile EMS wearable that, on spike
detection, *automatically* drives sub-fatigue muscle contraction to dispatch
glucose with minimal user effort — "set it and your physiology handles the spike."
Plus multi-signal control (combine with meal logging, heart rate, time-of-day).

- Risk: **High.** Automated EMS glucose dispatch raises comfort, safety, and
  efficacy-at-scale questions — but it rides the same sensor + controller platform.

---

## Honest open questions (the things that could kill it)

1. **CGM latency.** Interstitial glucose lags blood by ~5–15 minutes, so the
   trigger fires somewhat after the true rise begins. **Why it's probably OK:**
   postprandial curves climb over 30–60 minutes, so a 10-minute-lagged onset
   trigger still catches most of the rise — but this must be quantified, and
   predictive (meal-aware) triggering may be needed to buy back the lag.
2. **Is a *tolerable* dose of contraction enough?** The decisive question: does a
   protocol short and easy enough that people will actually do it *reliably*
   flatten spikes *enough* to matter? Soleus work suggests yes at low effort, but
   this is the make-or-break measurement.
3. **Adherence and friction.** A prompt to move 4–6 times a day must fit real life
   (at a desk, in a meeting). This is why the Tier-2/3 *seated, discreet, or
   assisted* contraction modes matter.
4. **Regulatory framing.** A drug-free wellness coaching loop is light-touch; an
   automated EMS "treatment" loop is a medical device. The product should start as
   the former and earn its way into the latter.

---

## Suggested first experiment (cheapest decisive test)

Recruit non-diabetic CGM users. Within-subject crossover across matched meals:
**(A)** standardized meal, no intervention (baseline spike);
**(B)** same meal, app dispatches a timed soleus/walk protocol at detected
spike-onset;
**(C)** same meal, same protocol but dispatched on a *predictive* (meal-logged)
trigger to beat CGM lag.
Primary readout: **postprandial glucose area-under-the-curve and peak** vs.
baseline. Secondary: adherence/effort rating.
If B meaningfully beats A — and C beats B by closing the latency gap — the entire
closed-loop thesis is validated for the cost of a small CGM behavioral study, with
**no hardware required.** That de-risks the wearable and EMS tiers.

---

## Value to the customer

- **The user (buyer):** A drug-free way to actually *flatten* spikes in real time,
  not just watch them — turning a CGM from a guilt-inducing dashboard into an
  active tool. Free to run, no side effects, immediate and personally measurable
  ("my spikes are visibly smaller on the days I follow the dispatch"). More stable
  energy, and a credible non-pharma path for the metabolic-curious and pre-diabetic.
- **CGM makers / wellness platforms:** A retention and differentiation feature that
  makes their sensor *do* something, deepening daily engagement and justifying
  subscription — a software moat on top of a commoditizing sensor.
- **Payers / employers:** A cheap, scalable, drug-free intervention for the huge
  pre-diabetic population, complementing (and triaging *before*) expensive GLP-1
  prescriptions.
- **Clinicians:** A quantified behavioral lever with an objective readout, usable
  for the metabolic-syndrome population that isn't yet on medication.

**The single sharpest value statement:** *the most powerful real-time
glucose-lowering tool you own is your own muscle — this is the first system that
dispatches it the instant you spike, drug-free, instead of just showing you the
spike after it's too late.*

---

## How this fits the pattern behind the earlier proposals

Same engine as glymphatic delivery, Grid Radar, and ReCharge:
- **Built from existing, shipped parts** (OTC CGM, known physiology, standard
  control) — the risk is efficacy/adherence, never "can the science work."
- **Slaves a system to a live signal we currently only *display*** (the glucose
  spike), the way the others exploited the brain's clearance cycle, the wire's
  echoes, and saturated sorbent media.
- **Has a cheap, decisive, hardware-free go/no-go experiment.**
- **Defines a new category** — *metabolic demand-response* — with an expansion path
  from app → confirming wearable → automated EMS dispatch.

And, per the lesson from the struck shortlist item: the novelty claim here is
**narrow, explicit, and checked against prior art** — drug-free *contraction-as-
actuator* closed loop for non-diabetics — rather than a broad "nobody's done
anything like this" assertion.
