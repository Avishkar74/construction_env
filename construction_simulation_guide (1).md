# Construction Project Simulation — Complete Reference Guide
> Real-world execution knowledge + MDP formulation + simulation code improvements
> *Canonical baseline: 1,000 sq. ft. G+1 residential project, Bengaluru, Karnataka*

---

## Table of Contents

1. [Project Lifecycle — End-to-End](#part-1--project-lifecycle)
2. [Task Breakdown — Micro Level](#part-2--task-breakdown)
3. [Workforce Management](#part-3--workforce-management)
4. [Material Planning](#part-4--material-planning)
5. [Equipment & Machinery](#part-5--equipment--machinery)
6. [Timeline & Scheduling](#part-6--timeline--scheduling)
7. [Real-World Constraints](#part-7--real-world-constraints)
8. [Decision-Making Framework](#part-8--decision-making)
9. [Complete Flow Summary with Formulas](#part-9--complete-flow-summary)
10. [Code Review & Improvement Recommendations](#part-10--code-improvements)

---

# PART 1 — Project Lifecycle

## Phase 0: Pre-Construction (Days -60 to 0)

This phase never appears in most simulations but shapes every constraint downstream. ~30% of Indian residential projects fail or overrun because of bad pre-construction decisions.

### Feasibility & Geotechnical Investigation

Bore logs determine the Safe Bearing Capacity (SBC) of the earth — this dictates the entire foundation design and is an absolute prerequisite before any structural drawings can be finalized.

**Bengaluru soil type guide:**

| Soil Type | Location Examples | SBC (T/m²) | Foundation Required |
|---|---|---|---|
| Hard gravel / rock | Indiranagar, Koramangala | 20–30 | Simple strip / isolated footings |
| Laterite soil | Whitefield, Sarjapur | 10–15 | Spread footings, heavier rebar |
| Black cotton soil | Tumkur Road, outskirts | 5–8 | Deeper footings or pile foundation (+₹15–40L) |

Standard bore test: 3–7 days. Other checks running in parallel:
- Topography survey: cut/fill volumes for earthwork
- Utility scan: locate existing water mains, sewers, power lines (missing these = catastrophic rework)
- FSI/FAR check: Floor Space Index determines legal build area

**Key Output:** Go/No-Go + project cost estimate ±30%

### Regulatory Approvals — Bengaluru Hard Constraint

**BBMP** (Bruhat Bengaluru Mahanagara Palike) or **BDA** (Bangalore Development Authority) approval is mandatory before excavation. This is a strict Finish-to-Start dependency — the simulation must treat it as an uncircumventable gating condition.

| Pathway | Timeline |
|---|---|
| Online submission, Green Belt Area (GBA) | 15–20 days |
| Manual processing, BDA plots outside GBA | 30–45 days |
| Disputed plots / heritage zone adjacency | 60–90 days |

**RL simulation note:** Commencing excavation without approval = terminal failure state (municipal demolition order). No reward should be available for actions that bypass this prerequisite.

### Budget Estimation

**Financial distribution for 1,000 sqft standard finish, Bengaluru:**

| Category | Share | Approximate Amount |
|---|---|---|
| Civil & structural works | ~35% | ₹10–14 lakh |
| Architectural finishing | ~30% | ₹9–12 lakh |
| MEP systems | ~15% | ₹4–6 lakh |
| Labour overheads + site running | ~15–20% | ₹4–6 lakh |

**Market rate:** ₹1,500–₂,500/sqft (standard), ₹3,000–₃,500/sqft (premium)

```
Total Cost = Direct × (1 + Indirect%) × (1 + Contingency%)

Direct:
  Civil works       = Area × sqft_rate
  MEP               = 15–25% of civil
  Finishing         = 20–35% of civil

Indirect:
  Site overheads    = 8–12%
  Contractor margin = 10–15%
  PM / supervision  = 3–5%

Contingency:
  Easy / standard   = 5%
  Complex           = 10–15%
  Hard / unknown    = 20%
```

---

# PART 2 — Task Breakdown (Micro Level)

## Phase 1: Site Preparation & Mobilisation (Days 1–5)

Site prep involves clearing vegetation, leveling ground, marking the structural grid using a total station or batter boards, and erecting temporary infrastructure. Accurate surveying is critical — the layout must match approved BBMP drawings exactly.

**Sequence:**
1. Fencing / hoarding site boundary
2. Demolition of existing structures (if any)
3. Topsoil stripping (150–300mm organic layer removed)
4. Temp facilities: site office, storage shed, water tank, generator
5. Structural grid layout using total station

| Sub-task | Duration | Workers (min / opt) | Materials | Equipment | Risks |
|---|---|---|---|---|---|
| Fencing & hoarding | 1 day | 4 / 6 | GI sheets, posts | Nil | Theft if delayed |
| Demolition | 1–3 days | 6 / 10 | Nil | JCB, sledgehammers | Hidden utilities |
| Topsoil stripping | 1 day | 3 / 5 | Nil | JCB / Dozer | Sticky soil in rain |
| Temp facilities | 1–2 days | 4 / 6 | Timber, GI sheets | Nil | None |
| Layout marking | 0.5 day | 1 Surveyor + 4 Helpers | Lime, pegs, string | Total station | Error propagates into foundation |

```
Workers_for_site_prep = ceil(Area_sqft / 250)
Min = 4 workers, Max = 15 for a standard residential plot
```

**Dependency:** Hard gate — must follow BBMP plan approval.

**Risk:** Boundary disputes or unmapped underground utilities can halt mobilisation entirely.

---

## Phase 2: Excavation & Foundation / Substructure (Days 6–18)

The foundation transfers the building's dead and live loads to the earth. Errors here cannot be corrected post-construction without massive cost. The internal sequence is a strict linear chain — no step can overlap the previous.

**Hard Finish-to-Start sequence:**
```
Bulk excavation → Manual pit excavation
  → PCC bed (M10 lean concrete, 75–100mm)
    → Footing rebar cage (Fe500D TMT)
      → Column starter bars
        → Shuttering / formwork
          → Concrete pour (M20/M25 — continuous, no cold joints)
            → Mandatory curing: 14–21 days
              → Backfill (compacted in 150mm layers)
```

| Sub-task | Duration | Workers (min / opt) | Key Materials | Equipment | Critical Risks |
|---|---|---|---|---|---|
| Bulk excavation | 2–4 days | 1 JCB op + 4 helpers | Nil | JCB / Excavator | Underground utilities, water table |
| Manual pit work | 2–3 days | 6 / 10 | Nil | Shovels, jack hammers | Trench collapse >1.5m without shoring |
| PCC bed | 0.5 day | 4 / 6 | Cement, aggregate | Transit mixer | Wrong w/c ratio = weak base |
| Rebar fabrication | 3–5 days | 3 Bar benders + 2 helpers | TMT Steel Fe500D | Bar bending machine | Wrong bar diameter = structural failure |
| Shuttering | 2–3 days | 2 Carpenters + 2 helpers | Plywood / steel shutters | Nil | Leakage during pour |
| Concrete pour | 1 day | 8 / 12 | Cement, aggregate, water | Transit mixer, vibrator, dewatering pump | Cold joint if interrupted |
| Curing | 14–21 days | 1 (monitoring / watering) | Water | Nil | Skipping = 30% compressive strength loss |
| Backfill | 1–2 days | 4 / 6 | Soil | Plate compactor | Poor compaction = differential settlement |

**Concrete volume formulas:**
```
Volume of footing (m³) = L × W × D
  e.g. 2.0m × 2.0m × 0.5m = 2.0 m³

Cement bags for M20 (1:1.5:3 mix):
  = Volume × 8.06 bags/m³ ≈ 16 bags per isolated footing

Steel weight formula:
  Weight (kg) = (D² / 162) × Length_metres
  where D = bar diameter in mm
```

**Monsoon risk (Bengaluru June–Sept):** Rain floods excavation trenches overnight — requires dewatering pumps and potentially re-excavating collapsed walls. Adds 3–7 days + ₹30,000–₹80,000 unplanned cost.

---

## Phase 3: Structural Framing — Columns, Beams, Slabs (Days 18–45)

Highest material consumption phase. Concrete slab pours must be continuous — any interruption beyond 30 minutes creates a cold joint (structural defect requiring expensive core-cutting to repair).

**Critical constraint — mandatory lag:** Concrete must reach 70% compressive strength before formwork removal. For M25 mix this is typically 7 days minimum, 28 days for full load bearing. Premature deshuttering causes catastrophic slab deflection or collapse. This lag cannot be expedited by adding labour — it is chemistry, not scheduling.

**Per-floor sequence:**
```
Plinth beam → Column raising (max 1.5m pour height per lift to prevent aggregate segregation)
  → Slab centering / false work
    → Beam shuttering
      → Slab rebar (bottom mesh → MEP conduits embedded → top mesh)
        → Slab concrete pour (one continuous operation)
          → Curing 14–21 days
            → Deshutter at 28 days (or structural engineer sign-off)
```

**Workers for structural frame (medium project):**

| Role | Count | Skill Level | CPWD Productivity Norm |
|---|---|---|---|
| Shuttering carpenters | 4–6 | Skilled | 20 sqm formwork/day |
| Bar benders / steel fixers | 4–6 | Skilled | 200 kg steel/day |
| Concrete gang (placing + vibrating) | 6–8 | Semi-skilled | Depends on pump output |
| Helpers (material carrying) | 6–10 | Unskilled | Support ratio |
| **Peak concreting day total** | **20–30** | | |

**Slab pour planning formula:**
```
Volume = L × W × Thickness = 30m × 12m × 0.125m = 45 m³
Transit mixers = ceil(45 / 6m³) = 8 trips (book 3 days in advance)
Pump rate = 30 m³/hr → pour time = 1.5 hrs
Total window = pour + setup + leveling + finishing ≈ 4.5 hrs

Mandatory weather check: no rain in 6-hour forecast before pour.
All rebar + conduit inspection must be signed off before concrete truck arrives.
```

---

## Phase 4: Masonry / Walls (Days 46–65)

Modern Bengaluru construction increasingly uses **AAC (Autoclaved Aerated Concrete) blocks** over traditional red clay bricks. AAC blocks are lighter (reduces slab dead load ~30%), thermally superior, and faster to lay — but more fragile and approximately 2× the cost per unit.

**Sequence:**
1. Wall layout marking on slab (matches approved floor plan)
2. First course in cement mortar (1:6 for AAC, thin-bed adhesive preferred)
3. Build to lintel level
4. Lintel concrete poured (over all door/window openings)
5. Wall completed to slab soffit level
6. Mortar joint curing — often skipped by unskilled crews, leading to shrinkage cracks

**CPWD productivity norms:**
- Mason brickwork: 1.0–1.25 cum/mason/day
- Mason AAC block work: 15–20 sqm/mason/day

**Worker allocation formula:**
```
Masons_needed = ceil(Wall_area_sqm / (Productivity × available_days))
              = ceil(300 / (12 × 15)) = 2 (minimum feasible)
Optimal = 3–4 masons
Helper ratio = 1.5 helpers per mason (CPWD standard)
```

**Material calculation (230mm brick wall):**
```
Bricks per sqm = 75–80
Mortar per sqm = 0.04 m³
Cement for 1:4 mortar = 0.04 × 7 bags/m³ = 0.28 bags/sqm
```

---

## Phase 5: MEP Rough-In (Days 61–75)

MEP rough-in runs parallel with later masonry floors but must be **100% complete and verified before any plastering begins** — hard Finish-to-Start constraint. Coordination failure here is the most common cause of expensive post-handover rework in Indian residential construction.

**Electrical sequence:**
1. Conduit routing plan from approved drawings
2. Chase cutting in walls (25mm PVC conduit slots)
3. Conduit fixed in chases with cement plaster fill
4. Draw wire pulled through conduit
5. Junction boxes and DB (Distribution Board) rough-in positioned

**Plumbing sequence:**
1. Soil stack routing (main vertical SWR drain pipe)
2. Horizontal drainage in slab — **must happen before slab pour** (hardest coordination point)
3. CPVC water supply pipe routing in wall chases
4. Vent pipe installation
5. **Pressure testing at 1.5× working pressure — mandatory sign-off before wall closure**

**Rework penalty for skipping pressure test:**
A plumbing leak discovered post-tiling requires: demolish tiles → demolish plaster → excavate wall → repair pipe → replaster → re-tile. Cost per bathroom: ₹50,000–₹2,00,000. Skipping MEP inspections historically inflates project costs by **12–30%** in post-handover warranty claims.

| Trade | Workers | Skill Level | Daily Rate (₹) |
|---|---|---|---|
| Licensed electrician | 2–3 | Highly skilled | 1,200–1,800 |
| Electrician helper | 2–3 | Semi-skilled | 600–800 |
| Plumber | 2–3 | Highly skilled | 1,000–1,500 |
| Plumber helper | 2 | Semi-skilled | 500–700 |

---

## Phase 6: Plastering & Waterproofing (Days 72–92)

**Sequence:**
1. Hack all RCC surfaces (chip to create adhesion key)
2. Apply chicken mesh at RCC-masonry interface (prevents crack propagation)
3. Internal walls: 12mm scratch coat → 8mm finish coat (P-sand + cement 1:4)
4. Wet areas: waterproofing compound slurry applied first (crystalline or APP)
5. External walls: 15mm cement plaster (weatherproof 1:3 mix)
6. Curing: 7 days minimum

**CPWD productivity:** Internal = 10–12 sqm/mason/day. External (with scaffolding) = 8–10 sqm/mason/day.

**Bengaluru monsoon constraint:** External plastering is physically impossible in heavy rain — wet mortar washes off before setting. Agent must redirect external plastering crew to internal tasks during rain/storm.

**Material formulas (12mm internal, 1:4 mix):**
```
Cement = Area × 0.073 bags/sqm
P-sand  = Area × 0.012 m³/sqm
```

---

## Phase 7: Flooring & Tiling (Days 90–104)

Internal plastering and ceiling work must be 100% complete before flooring — falling debris destroys newly laid tiles.

**Sequence:**
1. Floor base: 50mm cement screed, levelled to ±3mm tolerance
2. Waterproofing in wet areas (48hr cure before tiling)
3. Tile adhesive bed (6–10mm)
4. Tile setting from room centre outward, 2mm consistent joints
5. Epoxy or cement grouting
6. Skirting tiles
7. Final polishing and cleaning

**CPWD productivity:** 8–12 sqm/tile mason/day.

**Tile quantity formula:**
```
Floor tiles = (Floor_area / Tile_area) × 1.10  (10% wastage for cuts)
Skirting    = (Perimeter_m × Height_m / Tile_area) × 1.12

Example: 100 sqm floor, 600×600mm tiles:
  = (100 / 0.36) × 1.10 = 306 tiles
  Add skirting: 40m × 0.1m / 0.36 = 12 tiles
  Total: ~318 tiles → order 325 for safety
```

---

## Phase 8: Finishes, Fixtures & Handover (Days 100–125)

Late delivery of custom joinery (wardrobes, modular kitchens, UPVC windows) is the most common single cause of delayed handover.

**Sequence:**
1. UPVC / wooden window shutters installed
2. Door leaf hung (hinges, lock mortising)
3. Wall putty: 2 coats, 24hr drying between (wet putty under paint = bubbling later)
4. Primer coat
5. Paint: first coat → sand → second coat
6. Electrical faceplates, switches, light fixtures
7. Sanitary ware: WC, wash basin, shower mixer, flush valve
8. False ceiling (if any)
9. Snag list walkthrough → rectification → final client sign-off
10. BBMP completion certificate
11. As-built drawings + maintenance manual handed over

**Paint quantity formula:**
```
Coverage (interior emulsion) = 10–12 sqm/litre/coat
Paint_needed = (Total_wall_area / 10) × 2_coats × 1.15_wastage

For 1,000 sqft house: wall area ≈ 800 sqm
  = (800 / 10) × 2 × 1.15 = 184 litres → order 200 litres
```

**Real-world note:** While the critical path runs ~125 working days, actual Bengaluru projects span **250–365 calendar days** to absorb monsoon periods, financing gaps, and client-induced changes.

---

# PART 3 — Workforce Management

## How Worker Count Is Decided

**CPWD-based base formula:**
```
Required_Crew_Size = ceil(
    Total_Quantity_of_Work /
    (Target_Duration_Days × Daily_Productivity_per_Worker)
)

Example — Internal Plastering:
  Total area     = 300 sqm
  Target         = 10 days
  Productivity   = 10 sqm/mason/day
  Required masons = ceil(300 / (10 × 10)) = 3 masons
  Required helpers = 3 × 1.5 = 5 helpers (CPWD ratio)
```

**Crew size bands:**
```
Crew_min  = Required_workers × 0.75   (progress possible, slow)
Crew_opt  = Required_workers           (designed rate)
Crew_max  = Required_workers × 1.5    (hard ceiling before crowding begins)
```

## The Crowding Penalty (Critical Formula)

Over-staffing beyond the physical space threshold triggers a non-linear productivity collapse. A 1,000 sqft floorplate cannot accommodate more than ~15 active workers simultaneously without safety conflicts.

**CPWD-derived crowding formula:**
```
Effective_Productivity = Base_Productivity × max(0.4, 1.0 - λ × max(0, N_actual - N_optimal))

Where:
  N_actual  = workers assigned
  N_optimal = task's designed crew size
  λ         = spatial congestion penalty (0.08–0.15 per extra worker)

Example: Task designed for 5 masons, λ = 0.10, 10 masons assigned:
  = Base × max(0.4, 1.0 - 0.10 × (10 - 5))
  = Base × max(0.4, 0.5)
  = Base × 0.5   (50% productivity — 5 extra workers wasted)
```

**Simulation implementation options (choose one):**
```python
# Option A: Full crowding penalty (most realistic)
n_opt = self.required_workers
lambda_crowd = 0.10
above_opt = max(0, self.assigned_workers - n_opt)
crowd_factor = max(0.4, 1.0 - lambda_crowd * above_opt)
effective = min(self.assigned_workers, n_opt) + above_opt * crowd_factor
base_gain = 0.02 * effective

# Option B: Diminishing returns curve (simpler approximation)
effective = self.assigned_workers ** 0.85
base_gain = 0.02 * effective
```

## Worker Categories, Rates, and Productivity

| Category | Role | Daily Rate (Bengaluru ₹) | CPWD Productivity |
|---|---|---|---|
| Mason (brickwork) | Wall construction | 900–1,200 | 1.0–1.25 cum/day |
| Mason (plastering) | Wall finishing | 900–1,200 | 10–12 sqm/day |
| Mason (tiling) | Floor finishing | 1,000–1,300 | 8–12 sqm/day |
| Bar bender | Rebar fabrication + fixing | 1,000–1,400 | 200 kg/day |
| Shuttering carpenter | Formwork | 1,000–1,300 | 20 sqm/day |
| Licensed electrician | Wiring + fittings | 1,200–1,800 | 30m conduit/day |
| Plumber | Pipe fitting | 1,000–1,500 | 15m pipe/day |
| Painter | Wall finishing | 800–1,200 | 40 sqm/day |
| Unskilled helper | Support across all trades | 400–700 | Dependent on trade |
| Equipment operator | JCB, transit mixer | 1,000–1,600 | Equipment-dependent |

## Parallel vs Sequential Work

```
Sequential (hard physical dependency — cannot overlap):
  Foundation curing → Plinth beam → Column raising → Slab pour → Curing → Masonry

Parallel tracks (can run simultaneously after dependency unlock):
  After Foundation complete:
    ├── Structural columns (critical path)
    ├── Electrical conduit rough-in
    └── Plumbing drainage layout planning

  After Slab deshutter:
    ├── Masonry walls (critical path)
    ├── Roofing structure (separate gang)
    └── External scaffolding erection

  After Masonry + MEP rough-in:
    ├── Plastering (can overlap floors)
    └── Window / door frame fixing
```

## Labour Frictions and Seasonal Constraints

**Bengaluru migrant labour patterns:**
```
Absenteeism rates:
  Normal daily baseline  : 5–10%
  Festival periods       : 60–80% absent (Diwali, Onam, Pongal, Holi)
  Agricultural migration : 30–50% absent (harvest seasons)
  Monsoon weeks          : +10–15% additional absence

Simulation difficulty mapping:
  Easy   : 5%  daily absence probability
  Medium : 15% daily absence probability
  Hard   : 25% + seasonal spike events enabled
```

**Idle labour cost (dead capital):**
```
Daily_idle_cost = Workers_idle × Base_daily_rate

Unskilled idle = ₹400–700/worker/day wasted
Skilled idle   = ₹800–1,200/worker/day wasted

→ Must register as strong negative reward signal
→ This is the primary driver for JIT material ordering discipline
```

## Fatigue and Overtime Dynamics

```
Efficiency(t) = max(0.6, 1.0 - Fatigue_level × 0.4)

Fatigue accumulation:
  Per overtime hour beyond 8hrs = +0.05 fatigue
  5 consecutive 10hr days → fatigue ≈ 0.5, efficiency ≈ 0.80
  10 consecutive 10hr days → fatigue → 1.0, efficiency → 0.60

Fatigue recovery:
  Full rest day         = -0.10 to -0.15 fatigue
  Light-duty day (<50%) = -0.05 fatigue

Optimal overtime policy:
  Use ONLY when ALL conditions met:
  - Fatigue level < 0.30
  - Critical path task ≥ 2 days behind schedule
  - Budget used < 80%
  - Weather suitable for task type
```

---

# PART 4 — Material Planning

## Thumb Rules for 1,000 sqft RCC Framed House (CPWD / BSR Karnataka)

These are the industry-standard consumption constants used by Bengaluru site engineers for baseline procurement planning:

| Material | Consumption Constant | Total (1,000 sqft) | Notes |
|---|---|---|---|
| Cement (OPC 43 / PPC) | 0.40–0.48 bags/sqft | 400–480 bags (50kg each) | Check manufacture date |
| Reinforcement steel (TMT Fe500D) | 3.5–4.5 kg/sqft | 3,500–4,500 kg (3.5–4.5 MT) | Per structural drawings |
| M-Sand (fine aggregate) | 1.8–2.2 cft/sqft | 1,800–2,200 cft | Zone II, silt < 8% |
| Coarse aggregate (20mm) | 1.35–1.5 cft/sqft | 1,350–1,500 cft | Flakiness < 15% |
| Masonry units (bricks/AAC) | 1.45 sqft equiv/sqft BUA | ~1,450 sqft wall area | See phase 4 for unit conversion |
| Finishing tiles (floor + skirting) | 1.3 sqft/sqft BUA | 1,300 sqft | Includes 10% wastage |
| Paint (internal + external) | 0.15–0.20 litres/sqft | 150–200 litres | Premium brands 10–12 sqm/L |

## Why Materials Are NOT Ordered All at Once

Three compounding reasons make day-1 bulk ordering both impossible and penalisable:

**1. Spatial impossibility:**
480 cement bags + 4 MT steel + 2,200 cft sand occupies the entire 1,000 sqft plot. No room for machinery (JCB, mixers), worker movement, or task execution. Bengaluru urban plots frequently have no adjacent overflow space.

**2. Material degradation — cement quality decay formula:**
```
Quality_cement(t) = max(0, 1.0 - α × max(0, t_stored - Threshold_days))

Where:
  t_stored       = days since delivery
  Threshold_days = 90 (covered, dry storage) or 60 (monsoon / humid conditions)
  α              = 0.005 per day

Effect: cement stored 120 days loses ~15% quality → structurally unsafe
       cement stored 150 days loses ~30% quality → must be rejected

Simulation penalty for using degraded cement:
  → Apply structural penalty factor to affected task progress
  → Flag rework risk for downstream phases
```

**3. Financial suffocation:**
Tying up ₹15–20 lakh in materials on Day 1 kills working capital. Labour, equipment, and overhead costs still run daily. Most Bengaluru contractors operate on 30–40% working capital margins.

## JIT Procurement Lead Times (Bengaluru Market)

| Material | Easy (days) | Medium (days) | Hard (days) |
|---|---|---|---|
| Cement | 1–2 | 2–3 | 3–5 |
| TMT steel | 3–5 | 4–6 | 5–8 |
| M-sand / aggregate | 1–2 | 2–4 | 3–6 |
| AAC blocks / bricks | 2–4 | 3–5 | 4–7 |
| UPVC windows (standard) | 7–14 | 14–21 | 21–30 |
| UPVC windows (custom) | 21–30 | 30–45 | 45–60 |
| Sanitary ware | 3–7 | 7–14 | 14–21 |
| Elevator / lift | 90–120 | 120–150 | 150–180 |

**Elevator critical note:** Must be ordered at foundation stage (90-day minimum lead). Agents who don't pre-order this early in hard difficulty will have it on the critical path with zero room to recover.

## JIT Reorder Trigger Formula

```
Reorder_now = current_stock < (consumption_rate × (lead_time + safety_buffer))

Where:
  consumption_rate = material_per_10pct × 10 × daily_progress_rate
  safety_buffer    = 2 days (easy), 3 days (medium), 5 days (hard)

Order quantity:
  quantity = max(minimum_batch, deficit × 1.25)
  # 1.25 = 25% safety buffer above computed need
  # minimum_batch prevents uneconomic micro-orders
```

**Phase-locked ordering (dependency-aware ordering rules):**
```
DO NOT order before dependency is met:
  Tiles        → order only after internal plastering is ≥70% complete
  Doors/frames → after masonry openings measured (not before — custom sizing)
  Paint        → after putty application begins
  Sanitaryware → during plastering phase (4-week lead for premium brands)
  Elevator     → MUST order at foundation stage (90-day minimum)
```

## Complete Material List by Category

**Structural:**
| Material | Unit | Consumption per m³ | Quality Check |
|---|---|---|---|
| Cement OPC 43/53 | 50kg bag | 8.0 bags/m³ (M20) | Check manufacture date tag |
| TMT Steel Fe500D | kg | 75–85 kg/m³ RCC | TATA/JSW/Vizag preferred |
| Coarse aggregate 20mm | m³ | 0.9 m³/m³ concrete | Free from dust |
| M-Sand fine aggregate | m³ | 0.45 m³/m³ concrete | Zone II, no silt >8% |
| AAC blocks 200mm | nos | 10–12/sqm wall | Density 550–650 kg/m³ |
| Red bricks 230mm | nos | 75–80/sqm wall | Water absorption <15% |

**Finishing:**
| Material | Unit | Coverage | Ordering Trigger |
|---|---|---|---|
| Vitrified floor tiles | sqm | +10% waste | After screed level confirmed |
| Bathroom wall tiles | sqm | +12% waste | After plumbing rough-in tested |
| Interior emulsion paint | litre | 10–12 sqm/L/coat | After putty fully dry |
| Exterior texture paint | litre | 6–8 sqm/L/coat | Weather-resistant grade mandatory |
| Wall putty | kg | 0.8 kg/sqm/coat (×2) | After primer coat |
| Epoxy tile grout | kg | 0.35 kg/m joint | At tiling stage |

**MEP / Utilities:**
| Material | Unit | Notes |
|---|---|---|
| PVC conduit 25mm | metre | Power circuits |
| PVC conduit 20mm | metre | Control / low voltage |
| Electrical cables (Cu) | metre | Size per load calculation |
| MCBs + DB panels | nos | Per electrical design |
| CPVC pipe (hot water) | metre | Class 3 minimum |
| UPVC SWR pipe (drainage) | metre | Minimum 110mm soil stack |
| Sanitary ware | nos | Order during plastering phase |
| CP fittings (taps, mixers) | nos | Coordinate with tile pattern before ordering |

---

# PART 5 — Equipment & Machinery

| Equipment | Application | Duration | Bengaluru Market Cost | Key Constraints |
|---|---|---|---|---|
| Backhoe loader (JCB) | Site clearing, excavation, backfill | 2–5 days in substructure | ₹1,000–₁,200/hr | Cannot work in narrow spaces |
| Ajax Fiori transit mixer (6m³) | Large slab pours, mass concrete | 1–3 days per major pour | ₹9,000/day OR ₹1.2–2.5L/month | Book 3 days in advance |
| Concrete pump | High-reach slab pours | Per pour event | ₹8,000–₁2,000/day | Minimum 40m³ to justify mobilisation |
| Needle vibrators | Concrete compaction (all pours) | Every pour — intermittent | ₹500/day hire | MANDATORY — skipping causes honeycombing |
| Bar bending machine | Rebar fabrication | Foundation through slab | ₹2,000/day hire | Needs level hardstanding |
| Steel scaffolding + props | Slab formwork, external plastering | 60–90 days | ₹800–₁,200/bay/month | Curing delays escalate rental cost |
| Plate compactor | Backfill compaction | Earthwork phase | ₹1,500/day | Manual-guided |
| Tower crane | Multi-storey structures only | Full structure phase | ₹40,000–₆0,000/day | DGMS-licensed operator mandatory |
| Mobile crane | Material lifting for roof | As needed | ₹15,000–₂5,000/day | Outrigger space required |
| Wall chasing machine | MEP conduit slots | MEP phase | ₹800/day | Dust control required |
| Tile cutting machine | Flooring | Tiling phase | ₹1,200/day | Wet cutting preferred |
| Dewatering pump | Waterlogged trenches | Monsoon excavation | ₹1,500–₃,000/day | Mandatory near water table in monsoon |

**Equipment efficiency degradation formula:**
```
Effective_output = Rated_output × Health × Weather_modifier × Operator_skill_factor

Health degradation per working day:
  Normal use   = -0.02 to -0.03 health points
  Hard use     = -0.04 to -0.05 health points
Maintenance event = +0.15 to +0.25 health restoration

Weather modifiers:
  Tower crane in storm     = 0.0  (safety shutdown — must park)
  JCB in waterlogged soil  = 0.6  (traction loss)
  Transit mixer in rain    = 0.9  (enclosed drum, acceptable)
  All equipment in storm   = 0.2  (mobilisation only, no useful output)
```

---

# PART 6 — Timeline & Scheduling

## Critical Path Method (CPM)

The critical path is the longest unbroken chain of dependent tasks. Any delay on it delays the project by the same amount — there is no buffer.

```
For each task:
  ES (Early Start)  = max(EF of all predecessors)
  EF (Early Finish) = ES + Duration
  LS (Late Start)   = LF - Duration
  LF (Late Finish)  = min(LS of all successors)
  Float (Slack)     = LS - ES

Critical path = all tasks where Float = 0
```

**CPM for easy difficulty (5 tasks):**
```
Task 1 — Site Prep   (5d):  ES=1,  EF=5,  Float=0  ← CRITICAL
Task 2 — Foundation  (9d):  ES=6,  EF=14, Float=0  ← CRITICAL
Task 3 — Walls      (11d):  ES=15, EF=25, Float=0  ← CRITICAL
Task 4 — Roof        (7d):  ES=26, EF=32, Float=0  ← CRITICAL
Task 5 — Finishing   (8d):  ES=33, EF=40, Float=0  ← CRITICAL
                                        Project end = Day 40
```

**CPM for medium difficulty (parallel tracks):**
```
After Foundation (EF=14):
  Task 3 — Walls          : ES=15 (critical path continues)
  Task 6 — Electrical R/I : ES=14 (starts same day, parallel)
  Task 7 — Plumbing       : ES=14 (parallel)

Task 9 — Electrical Fitting: ES = max(EF_6=26, EF_7=28) = 28
Task 10 — Final Inspection : ES = max(32, 40, 28, 40) = 40 → EF=50
```

## Dependency Types in Construction

| Type | Definition | Construction Example |
|---|---|---|
| **Finish-to-Start (FS)** | B cannot start until A finishes | Plastering cannot start until MEP rough-in is 100% done |
| **Start-to-Start (SS)** | B can start when A starts | Soil disposal starts when excavation starts |
| **Mandatory Lag** | Fixed chemical wait, no workaround | Concrete curing: 14 days (cannot crash with labour) |

## CPM Action Masking for Simulation

```python
def get_valid_task_ids(obs) -> list[int]:
    """
    CPM-based action masking. Returns only task IDs that are
    physically ready for execution. Prevents agent from wasting
    actions on blocked / physically impossible tasks.
    """
    task_map = {t.task_id: t for t in obs.tasks}
    valid = []
    for task in obs.tasks:
        if task.status == "completed" or task.blocked:
            continue
        if obs.day < task.planned_start_day:
            continue
        deps_met = all(
            task_map.get(dep_id) is not None
            and task_map[dep_id].progress >= 1.0
            for dep_id in task.dependencies
        )
        mats_ok = all(
            obs.materials_available.get(mat, 0) >= rate * 0.1
            for mat, rate in (task.required_materials or {}).items()
        )
        if deps_met and mats_ok:
            valid.append(task.task_id)
    return valid
```

## Common Bottlenecks (Bengaluru Projects — Priority Order)

| Rank | Bottleneck | Typical Delay | Mitigation |
|---|---|---|---|
| 1 | Concrete curing (physics — non-negotiable) | 14–21 days always | Plan ahead; use curing compounds |
| 2 | Bengaluru monsoon (June–September) | 20–40 cumulative days | Indoor task buffer, waterproofing prep |
| 3 | BBMP approval delays | 15–45 days | Submit well in advance |
| 4 | Material delivery failures (steel, specialty) | 3–15 days | JIT with safety buffer |
| 5 | Labour unavailability (festivals / migration) | 5–15 days | Festival calendar in project schedule |
| 6 | Rework from quality failures | 7–30 days + cost | Mandatory inspection gates |
| 7 | Client design changes | 10–60 days (unpredictable) | Design freeze milestone |
| 8 | Equipment breakdown on critical day | 3–7 days | Spare machine on standby for pour days |

---

# PART 7 — Real-World Constraints

## Weather Impact — Bengaluru Monsoon (Quantified)

```
Weather modifier by task type:

OUTDOOR tasks (excavation, external plastering, external painting, roofing):
  Clear : 1.00
  Rain  : 0.60–0.70
  Storm : 0.15–0.20 (mostly stopped — safety shutdown)

CONCRETE POURS (special case — cannot pour in rain):
  Clear : 1.00
  Rain  : 0.00 (water changes w/c ratio → structural failure risk)
  Storm : 0.00 (immediate stop)

INDOOR tasks (electrical fitting, painting, tiling, plumbing fixtures):
  Clear : 1.00
  Rain  : 1.00 (completely unaffected)
  Storm : 0.90 (minor disruption from power cuts)
```

**Monsoon decision matrix — optimal agent policy:**
```
IF weather IN ("rain", "storm"):
  STOP  → external plastering (mortar washes off before setting)
  STOP  → concrete pours (w/c ratio disruption)
  STOP  → roofing (safety risk)
  STOP  → excavation (trench flooding)

  START / CONTINUE:
  ├── Internal MEP wiring (immune to weather)
  ├── Internal plastering (dry, sheltered)
  ├── Flooring and tiling (indoor)
  └── Painting prep (putty, primer if interior)

  CHECK → is dewatering pump needed for active excavation?
```

## Rework and Quality Frictions

Rework historically inflates Indian residential construction costs by **12–30%**. It is the dominant hidden cost that naive agents learn to ignore.

**Common rework triggers by phase:**

| Trigger | Discovery Phase | Rework Cost |
|---|---|---|
| Skipped plumbing pressure test | Post-tiling (leak visible) | ₹50,000–₂,00,000/bathroom |
| Cold joint in slab pour | Structural assessment | ₹1–5 lakh (core-cut + grout) |
| Premature deshuttering | Visible deflection | Potential demolition — ₹10–50 lakh |
| Floor not levelled to tolerance | Post-tiling inspection | ₹20,000–₈0,000/room |
| Wrong tile hollow spot | Post-occupancy cracking | ₹5,000–₂0,000/room |
| Degraded cement used | 28-day strength test fails | Structural rework at full cost |

**Rework simulation model:**
```python
def roll_quality_rework(self, tasks: dict) -> tuple:
    prob = {"easy": 0.02, "medium": 0.05, "hard": 0.10}[self.difficulty]
    issues = []
    for task in tasks.values():
        if 0.3 < task.true_progress < 0.9:
            if random.random() < prob:
                setback = random.uniform(0.05, 0.15)
                task.true_progress = max(0.0, task.true_progress - setback)
                issues.append(f"rework:{task.task_id}:{setback:.2f}")
    return tasks, issues
```

## Budget Overruns — Common Causes

| Cause | Typical Additional Cost |
|---|---|
| Client design changes | +5–20% of phase cost |
| Rework from quality failure | +12–30% of affected element |
| Material price escalation (steel) | +3–8% annually |
| Weather-extended duration | Labour cost × extra days |
| Equipment breakdown on critical day | ₹20,000–₁,00,000 |
| Elevator / UPVC ordered late | 15–45 days critical path impact |
| Subcontractor re-mobilisation | Premium of 10–20% on trade cost |

---

# PART 8 — Decision-Making Framework

## The Iron Triangle: Time, Cost, Quality

Every PM decision is a three-way trade-off. The RL agent must navigate the same constraints:

```
         TIME
         /\
        /  \
       /    \
   COST ──── QUALITY

Rules:
  Compress time  → costs more OR quality drops
  Improve quality → costs more OR takes longer
  Cut costs      → quality drops OR time extends

You can optimise any TWO — the third always suffers.
Agent reward must reflect all three simultaneously.
```

**Crashing the schedule (Time vs Cost):**
```
To recover N lost days on a critical task:
  Add extra workers → cost ↑ (and crowding penalty kicks in)
  Approve overtime  → cost ↑ + fatigue ↑
  Use RMC (Ready-Mix Concrete) → higher unit cost, faster pour

Crash cost per day saved = Additional_daily_cost / Days_recovered
Worth it ONLY IF: Crash_cost < Delay_penalty_per_day
Delay_penalty ≈ total_budget × 0.002 per day (typical liquidated damages)
```

**Resource leveling (smoothing demand peaks):**
```
Delay non-critical tasks (those with Float > 0) to:
  - Avoid peak labour demand (cash flow crunch)
  - Prevent site crowding (crowding penalty)
  - Maintain steady headcount

Float available = LS - ES for each non-critical task
Can delay by up to Float days without project impact
```

## Worker Allocation Decision Tree (Daily)

```
For each task, each day:

1. Is it on the critical path?
   YES → allocate first (top priority regardless of other signals)

2. Is it behind schedule (days_behind > 0)?
   YES → allocate proportionally more workers, up to Crew_max

3. Is it > 60% complete?
   YES → finish it first — near-completion tasks unlock downstream tasks faster

4. Are materials available (or arriving within lead time)?
   NO → DO NOT allocate workers — they will idle even if assigned

5. Are all dependencies complete?
   NO → skip — task cannot physically start

6. Is weather suitable for this task type?
   NO → skip outdoor tasks, redirect to indoor

Priority score:
  Score(task) = (is_critical × 100)
              + (priority_weight × 30)      # critical=3, high=2, medium=1
              + (days_behind × 50)
              + (progress > 0.6 × 80)       # near-completion bonus
              + ((1 - progress) × required_workers × 10)
              - (crowding_flag × 30)        # already over-staffed
```

## Material Ordering Decision

```
For each active or near-unlock task:
  needed_to_finish = amount_per_10pct × (remaining_progress × 10)
  have             = inventory[material]
  pending          = sum(pending_orders for this material)

  IF have + pending < needed_to_finish × 1.25:
      deficit = needed_to_finish × 1.25 - (have + pending)
      order(material, max(minimum_batch, deficit))

Near-unlock prefetch:
  IF one unmet dependency has progress >= 0.6:
      Pre-order 40% of materials needed for this task now
      (dependency will complete in ~5 days, material takes 3–5 days)
```

## Overtime Decision

```
Approve overtime ONLY when ALL true:
  ✓ Fatigue_level < 0.30
  ✓ Task is on critical path
  ✓ Task is >= 2 days behind schedule
  ✓ Budget_used < 80%
  ✓ Weather suitable for this task type

ROI check:
  Overtime_cost = workers × hours × ₹200/hr
  Delay_avoided = delay_penalty_per_day (₹5,000–₁5,000 for medium project)
  Approve if: Delay_avoided > Overtime_cost
```

## Trade-Off Matrix

| Situation | Option A | Option B | Recommended |
|---|---|---|---|
| Behind schedule + over budget | Crash (overtime) | Reduce scope | Reduce scope first, crash only critical path |
| Material short + idle workers | Wait for delivery | Reassign indoors | Reassign — idle cost is real and immediate |
| Storm day | Force outdoor work | Indoor reassignment | Indoor — outdoor modifier = 0.15–0.20 |
| Budget at 85%, 15 days left | Continue overtime | Stop overtime, extend | Stop overtime — reduce burn rate |
| Two critical tasks both behind | Split workers | Focus on one | Focus on the one closer to completion |
| Task > 60% complete, new task unlocked | Switch to new | Finish current | Finish current — unlock chain effect |

---

# PART 9 — Complete Flow Summary

## End-to-End Timeline: 1,000 sqft G+1 Residence, Bengaluru

| Timeline (Days) | Primary Phase | Core Agent Actions & Resource Logic | Materials Arriving |
|---|---|---|---|
| -30 to 0 | Pre-Construction | Secure BBMP approval. Soil test. Establish budget baseline | None |
| 1–5 | Site Prep & Mobilisation | Deploy JCB 1 day. 1 Surveyor + 4 Helpers. Erect hoarding | None |
| 6–15 | Foundation & PCC | Order initial cement + steel. 3 bar benders + 2 carpenters + 6–8 helpers | Cement batch 1, TMT steel |
| 16–25 | Plinth Beam + Backfill | Shutter → pour plinth beam → begin mandatory curing lag | Aggregate, binding wire |
| 26–45 | Ground Floor RCC Structure | 4–6 carpenters + 4–6 bar benders + 10–15 helpers. Book Ajax Fiori for slab | Cement batch 2, steel batch 2 |
| 46–60 | Slab Curing + Deshuttering | **14-day mandatory wait — physics, not scheduling.** 1 helper for watering | Order: AAC blocks, windows |
| 61–80 | Masonry (AAC Blocks) | 3–4 masons + 5–6 helpers. Carpenters prep first floor formwork simultaneously | AAC blocks, cement batch 3 |
| 81–95 | MEP Rough-In | 2 electricians + 2 plumbers + 3 helpers. Pressure-test before wall closure | Conduit, CPVC, SWR pipes |
| 96–120 | Plastering | 4 masons + 6 helpers. High cement + P-sand burn rate. External: monsoon check | Cement batch 4, P-sand |
| 121–140 | Flooring & Tiling | JIT tile order (placed during plastering). 3 tile masons + 3 helpers | Tiles, adhesive, grout |
| 141–160 | Carpentry, Doors, Primer | Install UPVC windows + wooden doors. Apply putty + primer coats | Window frames, putty, primer |
| 161–180 | Final Finishes + Handover | Install switches, sanitaryware. Snagging walkthrough. BBMP completion cert | Paint (200L), CP fittings |

## Key Simulation Formulas — Quick Reference

```python
# 1. Progress gain per task per day (crowding-aware)
n_opt = task.required_workers
lambda_crowd = 0.10
above_opt = max(0, assigned_workers - n_opt)
crowd_factor = max(0.4, 1.0 - lambda_crowd * above_opt)
effective_workers = min(assigned_workers, n_opt) + above_opt * crowd_factor

progress_gain = (
    0.02 * effective_workers
    * weather_modifier          # task-type-aware (indoor tasks = 1.0 always)
    * efficiency                # max(0.6, 1.0 - fatigue * 0.4)
    * material_gate             # 1.0 or 0.0
    * equipment_health_modifier # 0.4–1.0 for equipment-dependent tasks
)

# 2. Cement quality decay
def cement_quality(days_stored, covered=True):
    threshold = 90 if covered else 60
    alpha = 0.005
    return max(0.0, 1.0 - alpha * max(0, days_stored - threshold))

# 3. JIT reorder check
def should_reorder(mat, task, inventory, pending_qty, lead_time, safety=3):
    remaining = 1.0 - task.progress
    needed = task.required_materials.get(mat, 0) * remaining * 10
    have = inventory.get(mat, 0) + pending_qty
    rate = needed / max(1, task.planned_end_day - current_day)
    return have < rate * (lead_time + safety)

# 4. Fatigue-adjusted efficiency
efficiency = max(0.6, 1.0 - fatigue_level * 0.4)

# 5. Overtime ROI
delay_cost_per_day = total_budget * 0.002
overtime_cost = workers_on_task * overtime_hours * 200
approve_overtime = delay_cost_per_day > overtime_cost

# 6. Task priority score
def score(task):
    crowding = task.assigned_workers >= task.required_workers * 1.5
    return (
        (100 if task.is_critical_path else 0)
        + {"critical": 90, "high": 60, "medium": 30, "low": 0}[task.priority]
        + task.days_behind_schedule * 50
        + (80 if task.progress > 0.6 else 0)
        + (1.0 - task.progress) * task.required_workers * 10
        - (30 if crowding else 0)
    )
```

---

# PART 10 — Code Improvements

## 10.1 `task_module.py` — Critical Fixes

### Fix 1: Replace Linear Worker Scaling with Crowding-Aware Model

**Current (line ~95):**
```python
base_gain = 0.02 * self.assigned_workers  # linear — unrealistic
```

**Problem:** Linear scaling trains the agent to over-staff tasks. Dumping 20 workers onto a 5-worker task quadruples simulated progress — in reality it halves it.

```python
# Crowding-aware (most realistic):
n_opt = self.required_workers
lambda_crowd = 0.10
above_opt = max(0, self.assigned_workers - n_opt)
crowd_factor = max(0.4, 1.0 - lambda_crowd * above_opt)
effective = min(self.assigned_workers, n_opt) + above_opt * crowd_factor
base_gain = 0.02 * effective

# Simpler alternative (diminishing returns curve):
base_gain = 0.02 * (self.assigned_workers ** 0.85)
```

---

### Fix 2: Weather Modifier Must Be Task-Type Aware

**Problem:** Storm weather currently penalises indoor tasks (electrical fitting, painting, tiling) — this punishes the agent for making the correct decision to work indoors during bad weather.

```python
OUTDOOR_TASKS = {
    "Site Preparation", "Foundation", "Excavation",
    "Walls", "Roof", "Plastering", "Landscaping"
}
CONCRETE_TASKS = {"Foundation", "Structural Framing", "Walls"}

def _effective_weather_modifier(self, weather_modifier: float, weather: str) -> float:
    # Concrete pours: completely stopped in rain
    if self.title in CONCRETE_TASKS and weather in ("rain", "storm"):
        return 0.0
    # Indoor tasks: immune to weather
    if self.title not in OUTDOOR_TASKS:
        return 1.0
    return weather_modifier
```

---

### Fix 3: Material Consumption Logic Bug

**Problem:** `missing_now` list is mutated (items removed) mid-loop for "prep work" logic, then checked as `not missing_now` for consumption — these two purposes conflict, creating unpredictable blocking behaviour.

```python
# Clean separation:
def _check_material_status(self, materials_available, pending_orders, current_day, horizon):
    """Returns: (fully_available: bool, arriving_soon: list, blocking: list)"""
    blocking, arriving = [], []
    for mat, rate in self.required_materials.items():
        if materials_available.get(mat, 0) >= rate * 0.1:
            continue
        upcoming = [o for o in pending_orders
                    if o.material_type == mat
                    and o.arrival_day <= current_day + horizon]
        (arriving if upcoming else blocking).append(mat)
    return len(blocking) == 0 and len(arriving) == 0, arriving, blocking

def _consume_materials(self, materials_available, actual_gain):
    for mat, rate in self.required_materials.items():
        consume = rate * (actual_gain / 0.1)
        materials_available[mat] = max(0.0, materials_available.get(mat, 0) - consume)

# In update_progress():
fully_ok, arriving, blocking = self._check_material_status(
    materials_available, pending_orders, current_day, prep_horizon_days
)
if blocking:
    self.blocked = True
    self.status = "blocked"
    return 0.0
# ... compute gain ...
if actual_gain > 0:
    if arriving and not fully_ok:
        self.true_progress = min(prep_progress_cap, self.true_progress + gain)
    else:
        self.true_progress = min(1.0, self.true_progress + gain)
    actual_gain = self.true_progress - old_progress
    if fully_ok and actual_gain > 0:
        self._consume_materials(materials_available, actual_gain)
```

---

### Fix 4: Equipment Health Is a Dead Feature

**Problem:** `equipment_health` is tracked and degrades but is never read in `update_progress`. The degradation rolls are silently discarded.

```python
EQUIPMENT_DEPENDENT_TASKS = {
    "Site Preparation": "excavator",
    "Foundation": "excavator",
    "Structural Framing": "crane",
    "Walls": "crane",
    "Roof": "crane",
}

def update_progress(
    self,
    current_day: int,
    all_tasks: dict,
    weather_modifier: float,
    efficiency: float,
    materials_available: dict,
    pending_orders: list,
    equipment_health: dict = None,   # ADD THIS
    prep_horizon_days: int = 5,
    prep_progress_cap: float = 0.1,
) -> float:
    equip_modifier = 1.0
    if equipment_health:
        equip_key = EQUIPMENT_DEPENDENT_TASKS.get(self.title)
        if equip_key:
            equip_modifier = max(0.4, equipment_health.get(equip_key, 1.0))
    # ... then multiply:
    gain = base_gain * efficiency * effective_weather * equip_modifier
```

Update the call in `construction_env_environment.py`:
```python
total_gain = self._task_module.update_all(
    current_day=day,
    weather_modifier=weather_modifier,
    efficiency=self._state.worker_efficiency,
    materials_available=self._material_module.inventory,
    pending_orders=self._state.pending_orders,
    equipment_health=self._state.equipment_health,  # ADD THIS
)
```

---

## 10.2 `construction_env_environment.py` — Critical Fixes

### Fix 1: `bad_action` Is Never Set to True

**Problem:** `bad_action = False` is initialized but never changed. The `-1.5` reward penalty is dead code. The agent is never penalised for allocating to blocked or completed tasks.

```python
bad_action = False

for alloc in allocations:
    task_id = int(alloc.get("task_id", -1))
    task = self._task_module.tasks.get(task_id)

    # DETECT BAD ACTIONS (currently all missing):
    if task is None:
        bad_action = True
        continue
    if task.blocked or task.true_progress >= 1.0:
        bad_action = True       # ← THIS LINE IS MISSING
        continue
    if worker_count <= 0:
        continue
    # ... rest of allocation
```

---

### Fix 2: Budget Ratio Is Stale When Computing Reward

**Problem:** `budget_ratio` is computed before order costs are added to `total_cost`. The reward function sees an under-estimate, which under-penalises expensive ordering actions.

```python
# FIX — compute budget_ratio AFTER all costs applied:
self._state.total_cost = min(
    self._state.total_cost + step_cost,
    self._state.total_budget * 2.0
)
budget_ratio = self._state.total_cost / max(1.0, self._state.total_budget)  # fresh

reward, reward_components = self._compute_reward(
    progress_gain=progress_gain,
    weather=weather,
    bad_action=bad_action,
    budget_ratio=budget_ratio,   # now accurate
    day=day,
)
```

---

### Fix 3: Auto-Reschedule Does Not Preserve Task Duration

**Problem:** When `_auto_reschedule_ready_tasks` pulls a task forward (dependency met early), it updates `planned_start` but not `planned_end`. This creates phantom `days_behind_schedule` values when the task's `planned_end` is still the original date.

```python
def _auto_reschedule_ready_tasks(self, current_day: int) -> None:
    for task in self._task_module.tasks.values():
        if task.true_progress >= 1.0:
            continue
        if task.actual_start is not None:  # don't re-schedule in-progress tasks
            continue
        if not task.is_unblocked(self._task_module.tasks):
            continue

        original_duration = task.planned_end - task.planned_start

        if current_day < task.planned_start:
            # Pull forward — dependency met early
            task.planned_start = current_day
            task.planned_end = current_day + original_duration  # preserve duration
        elif current_day > task.planned_start:
            # Push back — task couldn't start on time
            task.planned_start = current_day
            task.planned_end = current_day + original_duration  # preserve duration
```

---

### Fix 4: Expose Equipment Health and Key Metrics to Agent

```python
# In _build_observation():
return ConstructionObservation(
    # ... existing fields ...
    equipment_health=dict(self._state.equipment_health),
    days_remaining=max(0, self._state.max_days - day),
    overall_progress=sum(t.true_progress for t in self._task_module.tasks.values())
                     / max(1, len(self._task_module.tasks)),
)
```

In `models.py`:
```python
class ConstructionObservation(Observation):
    # ... existing fields ...
    equipment_health: Dict[str, float] = Field(default_factory=dict)
    days_remaining: int = 0
    overall_progress: float = 0.0
```

---

## 10.3 `difficulty.py` — Improvements

### Fix 1: Hard Mode Missing Material Dependencies

8 of 9 hard-mode tasks (IDs 11–18) have `required_materials: {}`. Material management should be hardest at the hardest difficulty — currently it's trivial.

```python
# Realistic additions:
{"task_id": 11, "required_materials": {"steel": 5}},    # HVAC ductwork
{"task_id": 12, "required_materials": {"timber": 8}},   # Insulation backing frames
{"task_id": 13, "required_materials": {"cement": 3}},   # Flooring screed base
# task_id 16 (Elevator) already has steel:15 — correct
# tasks 14, 15, 17, 18 have no bulk materials — acceptable
```

### Fix 2: Add `paint` and `tiles` as Named Materials

Currently `paint` and tiles are referenced in task descriptions but not in difficulty.py `starting_materials`. Rename or add:

```python
DIFFICULTY_SETTINGS = {
    "medium": {
        "starting_materials": {
            "cement": 120, "steel": 60, "bricks": 300,
            "timber": 50,  "paint": 40,
            # Consider adding:
            "tiles": 0,    # ordered JIT, none on day 1
        }
    }
}
```

---

## 10.4 `event_module.py` — Add Missing Events

```python
def roll_material_delivery_delay(
    self, pending_orders: list
) -> tuple[list, list[str]]:
    """In-transit orders get delayed further — supplier or logistics issues."""
    prob = {"easy": 0.03, "medium": 0.08, "hard": 0.15}[self.difficulty]
    issues = []
    updated = []
    for order in pending_orders:
        if random.random() < prob:
            extra = random.randint(1, 3)
            order.arrival_day += extra
            issues.append(f"material_delay:{order.material_type}:{extra}d")
        updated.append(order)
    return updated, issues


def roll_quality_rework(self, tasks: dict) -> tuple[dict, list[str]]:
    """Random quality failures force progress regression."""
    prob = {"easy": 0.02, "medium": 0.05, "hard": 0.10}[self.difficulty]
    issues = []
    for task in tasks.values():
        if 0.3 < task.true_progress < 0.9:
            if random.random() < prob:
                setback = random.uniform(0.05, 0.15)
                task.true_progress = max(0.0, task.true_progress - setback)
                issues.append(f"rework:{task.task_id}:{setback:.2f}")
    return tasks, issues


def roll_price_escalation(
    self, material_costs: dict
) -> tuple[dict, list[str]]:
    """Occasional material price spikes (steel is most volatile in India)."""
    issues = []
    if self.difficulty == "hard" and random.random() < 0.05:
        mat = random.choice(["steel", "cement"])
        spike = random.uniform(1.05, 1.20)
        material_costs[mat] = material_costs.get(mat, 1.0) * spike
        issues.append(f"price_spike:{mat}:{spike:.2f}x")
    return material_costs, issues
```

---

## 10.5 `workforce_module.py` — Fixes

### Fix 1: Fatigue Recovery Is 4× Too Slow

`RECOVERY_PER_REST_DAY = 0.05` means 20 rest days to fully recover. In reality, a weekend (2 days) recovers most fatigue.

```python
RECOVERY_PER_ACTIVE_DAY = 0.02   # passive recovery even when working
RECOVERY_PER_REST_DAY   = 0.15   # significant recovery on low-activity days

def end_of_day(self, workers_used: int):
    self.overtime_approved_this_step = False
    utilisation = workers_used / max(1, self.total_workers)
    if utilisation < 0.5:
        self.fatigue = max(0.0, self.fatigue - self.RECOVERY_PER_REST_DAY)
    else:
        self.fatigue = max(0.0, self.fatigue - self.RECOVERY_PER_ACTIVE_DAY)
    self.efficiency = max(self.MIN_EFFICIENCY, 1.0 - (self.fatigue * 0.4))
```

### Fix 2: Overtime Cost Charges All Workers, Not Just Assigned

```python
# Current — charges ALL workers regardless of who worked overtime:
def overtime_cost(self, overtime_hours: int) -> float:
    return self.total_workers * overtime_hours * 200.0  # wrong

# Fixed:
def overtime_cost(self, overtime_hours: int, workers_on_task: int = None) -> float:
    n = workers_on_task if workers_on_task is not None else self.total_workers
    return n * overtime_hours * 200.0   # ₹200/worker/hr overtime premium
```

---

## 10.6 `material_module.py` — Add Cement Degradation

```python
MATERIAL_SHELF_LIFE_DAYS = {
    "cement": 90,    # covered storage, Bengaluru humidity
    "paint":  365,
    "steel":  9999,  # does not degrade if kept dry
    "bricks": 9999,
    "timber": 180,
}

class MaterialModule:
    def __init__(self):
        self.inventory: dict[str, float] = {}
        self.delivery_day: dict[str, int] = {}   # tracks age

    def get_cement_quality(self, current_day: int) -> float:
        delivered = self.delivery_day.get("cement", current_day)
        days_stored = current_day - delivered
        threshold = MATERIAL_SHELF_LIFE_DAYS["cement"]
        alpha = 0.005
        return max(0.0, 1.0 - alpha * max(0, days_stored - threshold))

    def process_deliveries(self, pending_orders, current_day: int):
        still_pending = []
        for order in pending_orders:
            if order.arrival_day <= current_day:
                self.inventory[order.material_type] = (
                    self.inventory.get(order.material_type, 0) + order.quantity
                )
                self.delivery_day[order.material_type] = current_day
            else:
                still_pending.append(order)
        return still_pending
```

---

## 10.7 `strategy_v7.py` — Policy Improvements

### Fix 1: Overtime Only Approved for Top Task

```python
# Extend to top 2 critical tasks; lower threshold from 3 to 2 days:
if obs.overtime_fatigue_level < 0.25:
    tasks = _ready_tasks(obs)
    tasks.sort(key=_task_score, reverse=True)
    for t in tasks[:2]:   # was tasks[0] only
        if t.is_critical_path and t.days_behind_schedule >= 2:  # was >= 3
            actions.append(ActionStep(
                action_type="approve_overtime",
                task_id=t.task_id,
                overtime_hours=2,
            ))
```

### Fix 2: `_task_score` Should Penalise Over-Staffed Tasks

```python
def _task_score(t: Any) -> float:
    score = 0.0
    if t.priority == "critical": score += 100.0
    elif t.priority == "high":   score += 70.0
    elif t.priority == "medium": score += 40.0

    remaining = (1.0 - t.progress) * max(1, t.required_workers)
    score += remaining * 10.0
    score += max(0, t.days_behind_schedule) * 50.0

    if t.progress > 0.6:
        score += 80.0   # near-completion bonus

    # Penalise already over-staffed tasks (crowding effect)
    if t.assigned_workers >= t.required_workers * 1.5:
        score -= 30.0

    return score
```

### Fix 3: Day-Estimate Lookahead for Prefetch

```python
def _prefetch_near_unlock_materials(obs: Any, lookahead_days: int = 7) -> list[ActionStep]:
    tasks = _tasks_by_id(obs)
    shortages: dict[str, float] = {}

    for t in obs.tasks:
        if t.progress >= 1.0:
            continue
        unmet = [tasks.get(dep_id) for dep_id in t.dependencies
                 if tasks.get(dep_id) is None or tasks[dep_id].progress < 1.0]

        unlock_in_days = 999
        for dep in unmet:
            if dep is None:
                continue
            remaining = 1.0 - dep.progress
            dep_workers = max(1, dep.assigned_workers)
            est_days = remaining / (0.02 * dep_workers ** 0.85)
            unlock_in_days = min(unlock_in_days, est_days)

        near_unlock = (not unmet) or (unlock_in_days <= lookahead_days)
        if not near_unlock:
            continue

        for mat, rate in (t.required_materials or {}).items():
            need = rate * 0.4
            have = float((obs.materials_available or {}).get(mat, 0.0)) \
                   + _get_pending_quantity(obs, mat)
            if have < need:
                shortages[mat] = shortages.get(mat, 0.0) + (need - have)

    if not shortages:
        return []

    return [
        ActionStep(action_type="order_material", material_type=mat,
                   quantity=max(40.0, deficit * 1.35))
        for mat, deficit in sorted(shortages.items(), key=lambda kv: kv[1], reverse=True)[:2]
    ]
```

---

## 10.8 `olamainference.py` — MDP Inference Upgrades

### Enhancement 1: CPM Action Masking

```python
# Add to olamainference.py or policies/utils.py:

def get_valid_task_ids(obs) -> list[int]:
    """
    CPM action masking. Prevents the agent from hallucinating
    actions on physically impossible or blocked tasks, saving
    inference tokens and eliminating false bad-action penalties.
    """
    task_map = {t.task_id: t for t in obs.tasks}
    valid = []
    for task in obs.tasks:
        if task.status == "completed" or task.blocked:
            continue
        if obs.day < task.planned_start_day:
            continue
        deps_met = all(
            task_map.get(dep_id) is not None
            and task_map[dep_id].progress >= 1.0
            for dep_id in task.dependencies
        )
        mats_ok = all(
            obs.materials_available.get(mat, 0) >= rate * 0.1
            for mat, rate in (task.required_materials or {}).items()
        )
        if deps_met and mats_ok:
            valid.append(task.task_id)
    return valid
```

### Enhancement 2: Enriched State Vector for LLM Prompting

```python
# In main() loop:
history_buffer = []

while (not result.done) and steps < MAX_STEPS:
    obs = result.observation
    valid_ids = get_valid_task_ids(obs)

    enriched_context = {
        "current_day": obs.day,
        "days_remaining": obs.max_days - obs.day,
        "overall_progress_pct": round(
            sum(t.progress for t in obs.tasks) / max(1, len(obs.tasks)) * 100, 1
        ),
        "weather": obs.weather,
        "valid_task_ids": valid_ids,
        "blocked_task_ids": [t.task_id for t in obs.tasks if t.blocked],
        "critical_tasks_behind": [
            {"id": t.task_id, "title": t.title, "days_behind": t.days_behind_schedule}
            for t in obs.tasks if t.is_critical_path and t.days_behind_schedule > 0
        ],
        "material_inventory": obs.materials_available,
        "pending_orders_count": len(obs.pending_orders or []),
        "workers_idle": obs.workers_available,
        "fatigue_level": obs.overtime_fatigue_level,
        "budget_used_pct": round(obs.budget_used * 100, 1),
        "pm_messages": obs.chat_messages,
    }

    action = smart_policy(obs)
    history_buffer.append({
        "day": obs.day,
        "context": enriched_context,
        "action": action.action_type
    })
```

### Enhancement 3: Iron Triangle Reward Decomposition

Decompose the final summary into the three PM dimensions for evaluation:

```python
# In main() summary block:
iron_triangle = {
    "time_performance": {
        "zero_progress_days": zero_progress_steps,
        "completion_score": round(completion_score, 4),
        "finished_within_budget_days": bool(result.done and steps < MAX_STEPS),
    },
    "cost_performance": {
        "idle_waste_total": round(
            reward_component_totals.get("idle_penalty", 0.0), 4
        ),
        "budget_pressure_total": round(
            reward_component_totals.get("budget_pressure", 0.0), 4
        ),
        "bad_action_penalties": round(
            reward_component_totals.get("bad_action", 0.0), 4
        ),
    },
    "quality_performance": {
        "delay_penalty_total": round(
            reward_component_totals.get("delay_penalty", 0.0), 4
        ),
        "weather_penalty_total": round(
            reward_component_totals.get("weather_penalty", 0.0), 4
        ),
        "efficiency_earned": round(
            reward_component_totals.get("efficiency", 0.0), 4
        ),
    },
}
summary["iron_triangle"] = iron_triangle
print(json.dumps(summary, indent=2))
```

---

## 10.9 Priority Matrix — All Improvements Ranked

| Priority | File | Issue | Impact on Agent Learning |
|---|---|---|---|
| 🔴 P0 | `construction_env_environment.py` | `bad_action` never set True | Agent never penalised for invalid allocations |
| 🔴 P0 | `construction_env_environment.py` | Budget ratio stale in reward | Reward mis-signals cost impact of orders |
| 🔴 P0 | `task_module.py` | Linear worker scaling | Trains agent to over-staff — wrong signal |
| 🔴 P0 | `task_module.py` | Equipment health unused | Tracked state, zero effect — wasted feature |
| 🟠 P1 | `task_module.py` | Weather hits indoor tasks equally | Punishes agent for correct indoor decisions |
| 🟠 P1 | `task_module.py` | Material check logic mutates mid-loop | Fragile, unpredictable blocking behaviour |
| 🟠 P1 | `construction_env_environment.py` | Auto-reschedule doesn't preserve duration | Phantom delay penalties accumulate |
| 🟠 P1 | `difficulty.py` | Hard mode: 8 tasks have no material deps | Material management trivial on hardest difficulty |
| 🟡 P2 | `event_module.py` | No material delay or rework events | Missing 2 most common real-world disruptions |
| 🟡 P2 | `workforce_module.py` | Fatigue recovery 4× too slow | Workers stay degraded unrealistically |
| 🟡 P2 | `workforce_module.py` | Overtime charges all workers | Over-charges budget, discourages overtime |
| 🟡 P2 | `strategy_v7.py` | Overtime only for 1 task, threshold too high | Misses second critical task; under-uses overtime |
| 🟡 P2 | `strategy_v7.py` | No crowding awareness in score | Assigns too many workers to a single task |
| 🟢 P3 | `material_module.py` | No cement degradation model | Missing physical realism, manageable gap |
| 🟢 P3 | `models.py` | Equipment health hidden from agent | Agent cannot make equipment-aware decisions |
| 🟢 P3 | `olamainference.py` | No CPM action masking | Agent can hallucinate invalid task IDs |
| 🟢 P3 | `olamainference.py` | 1D reward parsing only | Iron Triangle trade-offs invisible in logs |
