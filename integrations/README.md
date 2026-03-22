# Integrations — External Connectors & Mock Strategy

> This folder documents all third-party and mock integrations used by the project. The challenge allows mocks where direct platform APIs are unavailable. This folder shows exactly **what is real, what is simulated, and why**.

---

## Implementation Status

| Component | Status |
|-----------|--------|
| Integration inventory | ✅ Documented |
| Real-vs-mock classification | ✅ Documented |
| Mock strategy documentation | ✅ Documented |
| IMD Weather APIs (official) | ✅ Designed (exact endpoints mapped) |
| CPCB AQI API (OGD) | ✅ Designed (registration required) |
| OpenWeather API (fallback) | ✅ Designed (API key available) |
| TomTom API integration | ✅ Designed (API key available) |
| NewsAPI integration | ✅ Designed (API key available) |
| API-to-Defense mapping | ✅ Documented |
| Gemini API integration | ✅ Implemented |
| Payment sandbox | 📋 Planned |

---

## Integration Inventory

| # | Integration | Category | Source | Real / Mock | Why chosen |
|---|------------|----------|--------|-------------|-----------|
| 1 | **IMD Rainfall APIs** | Weather | India Meteorological Department | Real (free, official) | Official rain thresholds anchor T1–T3 triggers |
| 2 | **CPCB AQI API** | Air Quality | Central Pollution Control Board / OGD | Real (free, official) | Official AQI bands anchor T4–T5 triggers |
| 3 | **IMD Temperature APIs** | Temperature | India Meteorological Department | Real (free, official) | Official heat-wave criteria anchor T6–T8 triggers |
| 4 | **Traffic Data** | Traffic | TomTom / proxy | Premium (or mock) | Real-time traffic APIs for delay percentages |
| 5 | **Platform Outage Feed** | Platform | Delivery platform heartbeat | Mock | Platform APIs are unavailable; simulate outage events |
| 6 | **Demand Drop Signal** | Platform | Delivery platform order volume | Mock | Platform APIs are unavailable; simulate order drops |
| 7 | **Zone Closure Feed** | Civic | Municipal / police notices | Mock | No real-time API; simulate closure flags |
| 8 | **Payment Gateway** | Payout | UPI / payment sandbox | Mock | Actual payment integration not required for hackathon demo |
| 9 | **Bank Verification** | Identity | Banking API | Mock | Simulate bank account verification status |
| 10 | **Gemini AI** | Risk scoring | Google Gemini API | Real (API key) | AI-assisted risk assessment and claim narrative generation |
| 11 | **OpenWeather API** | Weather (fallback) | OpenWeather | Real (API key) | Fallback weather feed when IMD IP whitelisting is pending |
| 12 | **TomTom APIs** | Traffic / Anti-Spoofing | TomTom | Real (API key) | Traffic Flow, Incidents, Geofencing, Routing, Snap-to-Roads |
| 13 | **NewsAPI** | Civic / Context | NewsAPI | Real (API key) | Strike, protest, closure context; NOT a primary claims source |

---

## Data Source Priority

| Priority | Source Type | Examples |
|----------|-----------|---------| 
| **Primary** | Indian Government official APIs | IMD weather/rainfall, CPCB AQI, NDMA heat-wave guidance |
| **Secondary** | Commercial/proxy feeds | TomTom traffic, OpenWeather (fallback), NewsAPI context |
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

### Weather / Rainfall (Real — IMD Official APIs)
- **Source:** India Meteorological Department — Free, public APIs
- **IP Whitelisting Required:** Yes — email IMD with your server's public IP

**Exact APIs we use:**

| API | URL | Our trigger | What we extract |
|---|---|---|---|
| **District-wise Rainfall** | `mausam.imd.gov.in/api/districtwise_rainfall_api.php?id={obj_id}` | T1, T2, T3 | `Daily Actual` (mm), `Daily Category` |
| **District-wise Warnings** | `mausam.imd.gov.in/api/warnings_district_api.php?id={obj_id}` | T1, T2, T3 | Warning code 2=Heavy Rain, 16=Very Heavy, 17=Extremely Heavy; color 🟡🟠🔴 |
| **Current Weather** | `mausam.imd.gov.in/api/current_wx_api.php?id={station_id}` | T6, T7, T8 | `Temperature` (°C), `Last 24 hrs Rainfall` (mm), `Weather Code` |
| **City 7-Day Forecast** | `city.imd.gov.in/api/cityweather_loc.php?id={station_id}` | Premium pricing | `Today_Max_temp`, `Past_24_hrs_Rainfall`, 7-day forecast for zone risk |
| **District Nowcast** | `mausam.imd.gov.in/api/nowcast_district_api.php?id={obj_id}` | T1, T2, T3 | Cat7=Moderate rain, Cat12=Heavy rain, `color` code (1-4) |

**Station IDs for our 4 target cities:**

| City | Station Name | Station ID | Notes |
|---|---|---|---|
| Mumbai | Santacruz | 43057 | Primary rain trigger zone |
| Delhi | Safdarjung | 42182 | AQI + heat trigger zone |
| Bangalore | HAL Airport | 43296 | Traffic trigger zone |
| Hyderabad | Begumpet | 43128 | Multi-trigger zone |

**IMD field → DEVTrails trigger mapping:**
- `Past_24_hrs_Rainfall` ≥ 48mm → T1 (Watch)
- `Past_24_hrs_Rainfall` ≥ 64.5mm → T2 (Heavy Rain Claim)
- `Past_24_hrs_Rainfall` ≥ 115.6mm → T3 (Extreme Rain Escalation)
- Warning code `9` + `Temperature` ≥ 45°C → T6 (Heat Wave)
- Warning code `9` + `Temperature` ≥ 47°C → T7 (Severe Heat Wave)

**To get access:** Email IMD at their contact page with your server's public IP for whitelisting. Until then, seed CSVs simulate realistic readings within IMD bands.

### AQI (Real — CPCB / OGD API)
- **Source:** Central Pollution Control Board via Open Government Data portal (`data.gov.in`)
- **API Key Required:** Yes — free registration at `data.gov.in`
- **How to get access:**
  1. Register at `https://data.gov.in`
  2. Search for **"Real-Time Air Quality Index"**
  3. Click the dataset → Generate an API Key
  4. Use the API endpoint with your key
- **Official reference:** [CPCB National AQI](https://www.cpcb.nic.in/national-air-quality-index/) | [OGD AQI Dataset](https://www.data.gov.in/resource/real-time-air-quality-index-various-locations)
- **Data:** AQI value by city/station (PM2.5, PM10, SO2, NO2, O3, CO)
- **Thresholds used:** 201+ (Poor, caution), 301+ (Very Poor, claim), 401+ (Severe, escalation)
- **Triggers fed:** T4, T5
- **Demo note:** For demo, seed CSVs simulate AQI values matching CPCB category definitions.

### Heat / Temperature (Real — IMD Current Weather API)
- **Source:** Same IMD Current Weather API as rainfall
- **Exact API:** `mausam.imd.gov.in/api/current_wx_api.php?id={station_id}`
- **Fields used:** `Temperature` (current °C), `Weather Code`
- **Also:** District-wise Warnings API → Warning code `9` = Heat Wave, `10` = Hot Day
- **Official reference:** [IMD Heat Wave Warning](https://mausam.imd.gov.in/imd_latest/contents/pdf/pubbrochures/Heat%20Wave%20Warning%20Services.pdf) | [NDMA Heat Wave](https://ndma.gov.in/Natural-Hazards/Heat-Wave)
- **Thresholds used:** 45°C (heat-wave), 47°C (severe heat)
- **Triggers fed:** T6, T7, T8

### Traffic (Mock — TomTom in production)
- **Simulated data:** Travel delay percentage (0–100%)
- **Threshold used:** ≥ 40% delay
- **Triggers fed:** T9, T10, T11
- **Production API:** TomTom Traffic Flow API (paid per 1000 requests)

### Platform Outage / Demand (Mock)
- **Simulated data:** Outage duration (minutes), order volume drop (%)
- **Thresholds used:** ≥ 30 min outage, ≥ 35% demand drop
- **Triggers fed:** T12, T13
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

### OpenWeather API (Real — Fallback)
- **Purpose:** Fallback weather feed when IMD IP whitelisting is pending
- **Data:** Current and forecast weather conditions, rain intensity, temperature
- **Used for:**
  - Trigger validation fallback: rain risk (T1–T3), heat signals (T6–T8)
  - Event truth verification (Layer 1 of fraud pipeline)
- **Note:** IMD is the primary source. OpenWeather fills gaps until IMD access is live.
- **Consumer:** Trigger engine, fraud engine (event truth layer)

### TomTom APIs (Real — API Key)
- **Purpose:** Traffic disruption verification and anti-spoofing location validation
- **APIs used:**
  - **Traffic API / Traffic Flow API** — traffic delay percentage for T9–T11 triggers
  - **Traffic Incidents API** — disruption event detection
  - **Geofencing API** — zone boundary validation for anti-spoofing
  - **Routing API** — route plausibility checks
  - **Snap-to-Roads API** — verify GPS coordinates map to real roads
  - **Reverse Geocoding API** — location verification
- **Consumer:** Trigger engine, fraud engine (anti-spoofing layer), exposure matching

### NewsAPI (Real — API Key)
- **Purpose:** Civic disruption context and narrative enrichment
- **Data:** News articles about strikes, protests, closures, civic disruptions
- **Used for:**
  - Contextual disruption narrative in the admin dashboard
  - Trend enrichment for closure/strike triggers (T14, T15)
  - **NOT** a primary claims truth source — context only
- **Consumer:** Admin dashboard, trigger context enrichment

> [!WARNING]
> News data should support context and trend dashboards, but should **never** be the sole trigger truth source. All claims are validated against structured trigger data, not news headlines.

---

## Complete API Shopping List

> [!IMPORTANT]
> This is the exact list of APIs the project needs, organized by cost.

### Free (Indian Government / Open Source)

| API | Provider | Cost | What to do |
|---|---|---|---|
| District-wise Rainfall | IMD | Free | Email IMD your public IP for whitelisting |
| District-wise Warnings | IMD | Free | Same IP whitelisting as above |
| Current Weather | IMD | Free | Same IP whitelisting as above |
| City 7-Day Forecast | IMD | Free | Same IP whitelisting as above |
| District Nowcast | IMD | Free | Same IP whitelisting as above |
| Real-Time AQI | CPCB / data.gov.in | Free | Register at data.gov.in, generate API key |
| GDELT (news/events) | GDELT Project | Free | No key needed, open API |

### Free Tier Available

| API | Provider | Free tier | What to do |
|---|---|---|---|
| OpenWeather | OpenWeather | 1,000 calls/day free | Sign up at openweathermap.org |
| NewsAPI | NewsAPI | 100 requests/day free | Sign up at newsapi.org |
| Gemini AI | Google | Free tier available | Get API key from Google AI Studio |

### Premium (Production Only)

| API | Provider | Cost | When needed |
|---|---|---|---|
| TomTom Traffic | TomTom | ~$0.50/1000 requests | Production traffic triggers |
| WhatsApp Business | Twilio / Gupshup | Per-conversation | Production notifications |
| DigiLocker / Setu KYC | Government / Setu | Per-verification | KYC Level 4-5 |

---

## API-to-Defense Mapping

| API | Primary role | Anti-spoofing role | Dashboard role |
|---|---|---|---|
| **IMD Weather** | Hazard trigger validation (rain, heat) | Event truth verification — was the disruption real? | Weather severity feed |
| **CPCB AQI** | AQI trigger validation | Event truth — was air quality actually bad? | AQI severity display |
| **OpenWeather** | Fallback weather validation | Secondary event truth | Fallback weather feed |
| **TomTom Traffic** | Traffic disruption trigger (T9–T11) | Mobility plausibility — was traffic actually disrupted? | Traffic status |
| **TomTom Snap-to-Roads** | — | Route plausibility — was the worker on a real road? | — |
| **TomTom Geofencing** | Zone boundary definition | Geofence match — was the device in the zone? | Zone boundary |
| **NewsAPI** | Civic disruption context (T14, T15) | Contextual corroboration for closure/strike claims | News feed |
| **Gemini AI** | Claim narrative generation | — | AI explanation in review queue |

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
