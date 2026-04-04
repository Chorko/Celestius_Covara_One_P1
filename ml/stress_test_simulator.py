"""
Covara One — Financial Stress Test Simulator
Simulates a Prolonged 3-Day Monsoon across a national pool of 10,000 gig workers to prove Liquidity Circuit Breakers and target Actuarial BCR.
"""

import random

# Actuarial & Financial Baselines
TOTAL_WORKERS = 10000
WEEKLY_PREMIUM = 28
TOTAL_PREMIUM_POOL = TOTAL_WORKERS * WEEKLY_PREMIUM  # ₹280,000 weekly pool
ZONES = 10 # Spread across 10 regions to diversify spatial risk

def generate_worker():
    return {
        "hourly_income": random.uniform(50, 120),
        "shift_hours": random.uniform(6, 12),
        "active_days": random.randint(4, 7),
        "trust_score": random.uniform(0.6, 1.0),
        "gps_consistency_score": random.uniform(0.7, 1.0),
        "bank_verified": True,
        "accessibility_score": random.uniform(0.5, 1.0)
    }

def clip(val, min_val, max_val):
    return max(min_val, min(val, max_val))

def calc_payout(w, severity_s):
    b = 0.70 * w["hourly_income"] * w["shift_hours"] * w["active_days"]
    e = clip(0.45 + 0.30*(w["shift_hours"]/12.0) + 0.25*(1.0 - w["accessibility_score"]), 0.35, 1.0)
    c = clip(0.50 + 0.30*w["trust_score"] + 0.10*w["gps_consistency_score"] + 0.10, 0.45, 1.0)
    raw_payout = b * severity_s * e * c 
    # Use 1/6th of B as the daily fractional payout cap to prevent total drainage in one hit
    daily_fractional_cap = b / 6.0
    return min(daily_fractional_cap, min(3000.0, raw_payout))


def run_stress_test():
    workers = [generate_worker() for _ in range(TOTAL_WORKERS)]
    total_paid = 0

    print(f"🌊 COVARA ONE — CATASTROPHE STRESS TEST (SPATIAL DISTRIBUTION)")
    print(f"Workers: {TOTAL_WORKERS:,} (Distributed across {ZONES} independent geographic zones)")
    print(f"Total Weekly Premium: ₹{TOTAL_PREMIUM_POOL:,.2f}\n")

    # Disaster strikes ONE specific zone (representing 5% of total workers = 500 workers)
    affected_workers = 500

    # Day 1: Shock Event (120mm rain - Severity 0.9) - 60% of zone workers claim
    # Day 2: Continuing (90mm rain - Severity 0.7) - 40% of zone workers claim
    # Day 3: Receding (50mm rain - Severity 0.4) - 20% of zone workers claim
    scenarios = [
        {"day": 1, "severity": 0.9, "claim_rate": 0.60, "circuit_breaker_active": False},
        {"day": 2, "severity": 0.7, "claim_rate": 0.40, "circuit_breaker_active": True},
        {"day": 3, "severity": 0.4, "claim_rate": 0.20, "circuit_breaker_active": True},
    ]

    for s in scenarios:
        claimant_count = int(affected_workers * s["claim_rate"])
        claimants = random.sample(workers[:affected_workers], claimant_count)
        
        day_payout = 0
        held_by_breaker = 0

        for w in claimants:
            effective_severity = s["severity"] * 0.70 if s["circuit_breaker_active"] else s["severity"]
            payout = calc_payout(w, effective_severity)
            
            if random.random() < 0.05:
                continue # Rejected by fraud checking

            if s["circuit_breaker_active"]:
                if payout > 400 and random.random() < 0.2:
                    held_by_breaker += payout
                    continue 

            day_payout += payout

        total_paid += day_payout
        
        print(f"--- Day {s['day']} ---")
        print(f"Zone Claims Processed: {claimant_count:,}")
        if s["circuit_breaker_active"]:
            print(f"Circuit Breaker: ACTIVE (Severity throttled -30%, high-value escrowed)")
            print(f"Held in Escrow: ₹{held_by_breaker:,.2f}")
        print(f"Payout Issued: ₹{day_payout:,.2f}\n")


    # Calculate metrics
    loss_ratio = total_paid / TOTAL_PREMIUM_POOL
    burning_cost_rate = (total_paid * 1.1) / TOTAL_PREMIUM_POOL 
    
    print("============== FINAL FINANCIALS ==============")
    print(f"Total Premium Pool: ₹{TOTAL_PREMIUM_POOL:,.2f}")
    print(f"Total Affected Zone Payouts: ₹{total_paid:,.2f}")
    print(f"Final Loss Ratio: {loss_ratio:.2f}x")
    print(f"Burning Cost Rate (Expected): {burning_cost_rate:.2f}x")
    
    if loss_ratio <= 1.0:
        print("\n✅ RESULT: SUSTAINABLE.")
        print("By combining spatial risk diversification across 10 zones with our liquidity circuit breakers,")
        print(f"the insurer survived a 3-day max-severity event in a major hub with a Loss Ratio of {loss_ratio:.2f}.")
    else:
        print("\n❌ RESULT: INSOLVENT. Pool drained.")


if __name__ == "__main__":
    run_stress_test()
