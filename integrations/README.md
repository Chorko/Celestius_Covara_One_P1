# Integrations — External Connectors & Mock Strategy

> This folder documents all third-party and mock integrations used by the project. The challenge allows mocks where direct platform APIs are unavailable. This folder shows exactly **what is real, what is simulated, and why**.

---

## Implementation Status

| Component | Status |
|-----------|--------|
| Integration inventory | ✅ Documented |
| Real-vs-mock classification | ✅ Documented |
| Mock strategy documentation | ✅ Documented |
| OpenWeather API integration | ✅ Designed (API key available) |
| TomTom API integration | ✅ Designed (API key available) |
| NewsAPI integration | ✅ Designed (API key available) |
| API-to-Defense mapping | ✅ Documented |
| Weather API connector (IMD/OGD) | 📋 Planned |
| AQI API connector (CPCB/OGD) | 📋 Planned |
| Payment sandbox | 📋 Planned |
| Gemini API integration | ✅ Implemented |

---

## Integration Inventory

| # | Integration | Category | Source | Real / Mock | Why chosen |
|---|------------|----------|--------|-------------|-----------|
| 1 | **IMD Rainfall Data** | Weather | India Meteorological Department / OGD | Real (public) | Official rain thresholds anchor T1–T3 triggers |
| 2 | **CPCB AQI Data** | Air Quality | Central Pollution Control Board / OGD | Real (public) | Official AQI bands anchor T5–T6 triggers |
| 3 | **IMD/NDMA Heat Data** | Temperature | India Meteorological Department | Real (public) | Official heat-wave criteria anchor T7–T9 triggers |
| 4 | **Traffic Data** | Traffic | Google Maps API / proxy | Mock | Real-time traffic APIs are expensive; use proxy/mock for delay percentages |
| 5 | **Platform Outage Feed** | Platform | Delivery platform heartbeat | Mock | Platform APIs are unavailable; simulate outage events |
| 6 | **Demand Drop Signal** | Platform | Delivery platform order volume | Mock | Platform APIs are unavailable; simulate order drops |
| 7 | **Zone Closure Feed** | Civic | Municipal / police notices | Mock | No real-time API; simulate closure flags |
| 8 | **Payment Gateway** | Payout | UPI / payment sandbox | Mock | Actual payment integration not required for hackathon demo |
| 9 | **Bank Verification** | Identity | Banking API | Mock | Simulate bank account verification status |
| 10 | **Gemini AI** | Risk scoring | Google Gemini API | Real (API key) | AI-assisted risk assessment and claim narrative generation |
| 11 | **OpenWeather API** | Weather / Trigger | OpenWeather | Real (API key) | Weather severity feed, rain risk, temperature / heat signals for trigger validation |
| 12 | **TomTom APIs** | Traffic / Anti-Spoofing | TomTom | Real (API key) | Traffic Flow, Incidents, Geofencing, Routing, Snap-to-Roads, Reverse Geocoding for disruption verification and anti-spoofing |
| 13 | **NewsAPI** | Civic / Context | NewsAPI | Real (API key) | Strike, protest, closure context; narrative intelligence for dashboards; NOT a primary claims source |
| 14 | **Guidewire Cloud APIs** | Insurer Workflow | Guidewire | Future integration | Organizational reference for policy, claims, billing, and party domain mapping |

---

## Data Source Priority

Following the expert-session guidance:

| Priority | Source Type | Examples |
|----------|-----------|---------|
| **Primary** | Government public data | IMD weather/rainfall, CPCB AQI, NDMA heat-wave guidance |
| **Secondary** | Commercial/proxy feeds | Traffic delay proxies, route-time APIs |
| **Tertiary** | Simulated data | Platform outage, demand collapse, zone closures |

---

## Mock Strategy

### Why mocks are necessary
Platform-specific APIs (delivery order volume, outage heartbeats, GPS traces) are **not publicly available**. The challenge explicitly allows mocks where direct APIs are unavailable.

### How mocks are built
- Grounded in **realistic parameters** — e.g., traffic delay percentages based on typical urban congestion ranges
- Bounded by **public threshold values** — rain mocks stay within IMD bands, AQI mocks within CPCB categories
- Generated through the **synthetic data endpoint** — `GET /mock-data/generate` produces consistent worker + trigger datasets
- **Documented with assumptions** — every mock value has a documented range and rationale

### What is NOT mocked
- Trigger threshold logic (uses real public thresholds)
- Premium/payout formulas (uses documented mathematical formulas)
- Fraud detection logic (uses rule-based scoring)
- Claim pipeline stages (uses deterministic business rules)

---

## Integration Details

### Weather / Rainfall (Real — Public)
- **Source:** IMD operational data via OGD portal
- **Official reference:** [IMD Rainfall FAQ](https://rsmcnewdelhi.imd.gov.in/images/pdf/faq.pdf) | [IMD Heavy Rainfall Warning](https://mausam.imd.gov.in/imd_latest/contents/pdf/pubbrochures/Heavy%20Rainfall%20Warning%20Services.pdf)
- **Data:** 24-hour rainfall in mm by city/zone
- **Thresholds used:** 48mm (watch), 64.5mm (heavy), 115.6mm (very heavy+)
- **Triggers fed:** T1, T2, T3
- **Demo-stage note:** Public data is accessible via OGD APIs or downloadable datasets. For demo, seed CSVs simulate realistic rainfall readings within IMD bands.

### AQI (Real — Public)
- **Source:** CPCB National AQI monitoring via OGD repository
- **Official reference:** [CPCB National AQI](https://www.cpcb.nic.in/national-air-quality-index/) | [OGD AQI Dataset](https://www.data.gov.in/resource/real-time-air-quality-index-various-locations)
- **Data:** AQI value by city/station
- **Thresholds used:** 201+ (caution), 301+ (severe), 401+ (extreme)
- **Triggers fed:** T5, T6
- **Demo-stage note:** CPCB publishes real-time AQI through its dashboard and OGD. For demo, seed CSVs simulate AQI values matching CPCB category definitions.

### Heat / Temperature (Real — Public)
- **Source:** IMD temperature readings, NDMA heat-wave guidance
- **Official reference:** [IMD Heat Wave Warning](https://mausam.imd.gov.in/imd_latest/contents/pdf/pubbrochures/Heat%20Wave%20Warning%20Services.pdf) | [NDMA Heat Wave](https://ndma.gov.in/Natural-Hazards/Heat-Wave)
- **Data:** Temperature in °C, heat-wave condition flags
- **Thresholds used:** 45°C (heat-wave), 47°C (severe heat)
- **Triggers fed:** T7, T8, T9
- **Demo-stage note:** IMD/NDMA publish heat-wave criteria and alerts publicly. Seed CSVs include realistic temp values within IMD classification ranges.

### Traffic (Mock)
- **Simulated data:** Travel delay percentage (0–100%)
- **Threshold used:** ≥ 40% delay
- **Triggers fed:** T12
- **Assumption:** Delay percentage models urban congestion patterns during disruption events

### Platform Outage / Demand (Mock)
- **Simulated data:** Outage duration (minutes), order volume drop (%)
- **Thresholds used:** ≥ 30 min outage, ≥ 35% demand drop
- **Triggers fed:** T13, T14
- **Assumption:** Based on typical gig-platform disruption patterns

### Payment Gateway (Mock)
- **Purpose:** Simulate UPI/gateway payout confirmation
- **Output:** Payment status (success/pending/failed), transaction ID
- **Consumer:** Payout service, worker dashboard

### Bank Verification (Mock)
- **Purpose:** Simulate bank account verification
- **Output:** Verification status (verified/pending/failed)
- **Consumer:** Fraud engine (Layer 4), payout service

### Gemini AI (Real — API Key)
- **Purpose:** AI-assisted risk analysis, claim narrative generation, and review queue explanation
- **Integration:** Google Gemini API with key rotation
- **Consumer:** Claim pipeline (Gemini narrative stage), insurer review queue

### OpenWeather API (Real — API Key)
- **Purpose:** Weather severity feed for trigger validation
- **Data:** Current and forecast weather conditions, rain intensity, temperature, heat signals
- **Used for:**
  - Trigger validation: rain risk (T1–T3), heat signals (T7–T9)
  - Event truth verification (Layer 1 of fraud pipeline)
  - Near-real-time disruption monitoring
- **Consumer:** Trigger engine, fraud engine (event truth layer)

### TomTom APIs (Real — API Key)
- **Purpose:** Traffic disruption verification and anti-spoofing location validation
- **APIs used:**
  - **Traffic API / Traffic Flow API** — traffic delay percentage for T12 trigger
  - **Traffic Incidents API** — disruption event detection
  - **Geofencing API** — zone boundary validation for anti-spoofing
  - **Routing API** — route plausibility checks
  - **Snap-to-Roads API** — verify GPS coordinates map to real roads (anti-spoofing)
  - **Reverse Geocoding API** — location verification
  - **Matrix Routing / Waypoint Optimization** — route stress analysis where helpful
- **Used for:**
  - Disruption verification (traffic collapse, route inaccessibility)
  - Zone match confidence
  - Route accessibility scoring
  - **Anti-spoofing logic** — confirming claimed location is on a real delivery route
  - Geofence-based evidence checks
- **Consumer:** Trigger engine, fraud engine (anti-spoofing layer), exposure matching

### NewsAPI (Real — API Key)
- **Purpose:** Civic disruption context and narrative enrichment
- **Data:** News articles about strikes, protests, closures, civic disruptions
- **Used for:**
  - Contextual disruption narrative in the admin dashboard
  - Trend enrichment for closure/strike triggers (T10, T11)
  - **NOT** a primary claims truth source — context only
- **Consumer:** Admin dashboard, trigger context enrichment

> [!WARNING]
> News data should support context and trend dashboards, but should **never** be the sole trigger truth source. All claims are validated against structured trigger data, not news headlines.

### Guidewire Cloud APIs (Future — Organizational Reference)
- **Purpose:** Future insurer workflow integration
- **Conceptual mapping:**
  - Policy / quote / renewal → `backend/app/routers/policies.py`
  - Claims / FNOL / review → `backend/app/routers/claims.py`
  - Billing / payout / payment → `backend/app/routers/payouts.py` (planned)
  - Customer / party / identity → `backend/app/routers/workers.py`
  - Document / evidence → evidence service
  - Analytics / event / integration → `backend/app/routers/analytics.py`
- **Note:** Used only as organizational / future integration guidance, not as proof that DEVTrails is currently running on Guidewire

---

## API-to-Defense Mapping

How each API contributes to the platform's defense layers:

| API | Primary role | Anti-spoofing role | Dashboard role |
|---|---|---|---|
| **OpenWeather** | Hazard trigger validation (rain, heat) | Event truth verification — was the disruption real? | Weather severity feed display |
| **TomTom Traffic / Incidents** | Traffic disruption trigger (T12) | Mobility plausibility — was traffic actually disrupted? | Traffic status in zone view |
| **TomTom Snap-to-Roads** | — | Route plausibility — was the worker on a real road? | — |
| **TomTom Geofencing** | Zone boundary definition | Geofence match — was the device inside the operating zone? | Zone boundary visualization |
| **TomTom Routing** | Route accessibility scoring | — | Route stress display |
| **NewsAPI** | Civic disruption context (T10, T11) | Contextual corroboration for closure/strike claims | News feed in admin dashboard |
| **Gemini AI** | Claim narrative generation | — | AI explanation in review queue |
| **Guidewire** | Future insurer workflow integration | — | — |

---

## Inputs

| Input | Source |
|-------|--------|
| City and zone identifiers | Worker profile / API request |
| Date and time range | Trigger monitoring schedule |
| Policy or payout request | Claim engine / payout service |

## Outputs

| Output | Consumer |
|--------|----------|
| Normalized trigger data (rain, AQI, heat, traffic, etc.) | Trigger engine, data layer |
| Payment confirmation (mock) | Payout service, worker dashboard |
| Bank verification result (mock) | Fraud engine, payout service |
| AI analysis response | Risk scoring, premium calculation |

---

## Why This Folder Matters

Judges need to know **exactly** what data is real and what is simulated. A transparent mock strategy with documented assumptions is more credible than hiding behind vague "API integration" claims. This folder proves we know the difference and designed the system to work with either real or mock data sources. Every API is mapped to its specific role in trigger validation, anti-spoofing defense, and dashboard context.
