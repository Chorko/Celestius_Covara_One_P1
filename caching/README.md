# Caching — Cache Strategy & TTL Policies

> External signal fetching, repeated dashboard loading, and repeated claim simulations can create unnecessary load. The cache avoids repeated recomputation and makes the demo feel fast.

---

## Implementation Status

| Component | Status |
|-----------|--------|
| Cache strategy definition | 📝 Documented |
| TTL policy specification | 📝 Documented |
| Invalidation rules | 📝 Documented |
| Redis integration | 📋 Planned |
| Cache middleware | 📋 Planned |

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Cache store | **Redis** | In-memory key-value store with TTL support, widely used, easy to integrate with FastAPI |

---

## What Gets Cached

| Cache Target | TTL | Key Pattern | Why cache it |
|-------------|-----|-------------|-------------|
| Trigger feeds by city/zone | **5 min** | `trigger:{city}:{zone}` | Avoid repeated external API calls during active monitoring |
| Threshold lookup tables | **24 hr** | `thresholds:{type}` | Static reference data; rarely changes |
| Dashboard summary cards | **2 min** | `dashboard:{type}:{scope}` | Reduce DB aggregation on repeated dashboard loads |
| Generated mock datasets | **30 min** | `mockdata:{city}:{days}` | Avoid regenerating identical synthetic data |
| Scenario simulation outputs | **10 min** | `sim:{worker_id}:{trigger_id}` | Same scenario re-run should return cached result |
| Premium quote results | **5 min** | `quote:{worker_id}:{week}` | Avoid recalculation on page refresh |

---

## Cache Invalidation Strategy

| Event | Invalidation action |
|-------|-------------------|
| New trigger event ingested | Invalidate `trigger:{city}:{zone}` for affected zone |
| Claim decision made | Invalidate `dashboard:*` for affected scope |
| Policy activated or renewed | Invalidate `quote:{worker_id}:*` |
| Mock data regenerated | Invalidate `mockdata:{city}:*` |
| Threshold configuration updated | Invalidate `thresholds:*` |

**General rule:** Prefer short TTLs over complex invalidation logic. For a hackathon demo, staleness of a few minutes is acceptable; correctness on cache miss is mandatory.

---

## Cache Flow

```mermaid
flowchart LR
    REQ["API Request"]
    RC{"Redis<br/>Cache Hit?"}
    RS["Return Cached<br/>Response"]
    BE["Backend<br/>Service"]
    WR["Write to<br/>Cache"]
    RR["Return Fresh<br/>Response"]

    REQ --> RC
    RC -- "Hit" --> RS
    RC -- "Miss" --> BE
    BE --> WR
    WR --> RR

    style RC fill:#f39c12,color:#fff
    style RS fill:#2ecc71,color:#fff
    style RR fill:#4a9eff,color:#fff
```

---

## Inputs

| Input | Description |
|-------|-------------|
| City identifier | Scopes trigger and mock-data caches |
| Zone identifier | Scopes trigger feed caches |
| Date range | Scopes temporal queries |
| Trigger type | Scopes threshold lookups |
| Simulation request key | Composite key for scenario caching |

## Outputs

| Output | Description |
|--------|-------------|
| Cached JSON payload | Stored response for cache hits |
| Cache hit/miss metadata | Used for monitoring and debugging |
| Cache headers | `X-Cache: HIT` or `X-Cache: MISS` in API responses |

## Downstream

The cached response is returned to **backend services** and then surfaced to the **frontend dashboards**. Cache sits between the API gateway and the service layer.

---

## Why This Folder Exists

This folder exists so we do not repeatedly fetch or recompute the same environmental signal logic during demos. When a judge refreshes the dashboard or re-runs a scenario, the response should be fast and consistent. The caching layer makes the system feel production-ready even during a hackathon demonstration.
