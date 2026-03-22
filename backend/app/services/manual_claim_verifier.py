"""
DEVTrails — Manual Claim Verifier

Manual claims undergo stricter scrutiny than trigger-driven batch claims.
This service evaluates evidence completeness, geo-confidence, and provides
clear "why held" explanations.
"""

from datetime import datetime
from backend.app.services.geo_verification import verify_zone_match


def evaluate_manual_claim(
    claim_record: dict, evidence_records: list[dict], worker_context: dict
) -> dict:
    """
    Evaluates a single manual claim based on its attached evidence.
    """
    hold_reasons = []

    # 1. Evidence Completeness Score
    evidence_types = {e.get("evidence_type") for e in evidence_records}

    compl_score = 0.0
    if "photo" in evidence_types or "video" in evidence_types:
        compl_score += 0.5
    if "text" in evidence_types:
        compl_score += 0.2

    stated_geo_exists = claim_record.get("stated_lat") is not None
    exif_geo_exists = any(
        e.get("exif_lat") is not None for e in evidence_records
    )

    if stated_geo_exists or exif_geo_exists:
        compl_score += 0.3

    if compl_score < 0.7:
        hold_reasons.append(
            f"Incomplete evidence (score: {compl_score}). Need at least photo/video and location."
        )

    # 2. Geo-confidence & Zone Match Check
    geo_score = 1.0
    if not worker_context.get("gps_consent"):
        geo_score -= 0.3
        hold_reasons.append("Worker has not consented to GPS tracking.")

    if not stated_geo_exists and not exif_geo_exists:
        geo_score -= 0.5
        hold_reasons.append(
            "No geographic location provided with claim or evidence."
        )

    # Check Zone Distance
    zone_data = worker_context.get("zones", {})
    zone_lat = zone_data.get("center_lat")
    zone_lng = zone_data.get("center_lng")

    if zone_lat and zone_lng:
        # Prefer true EXIF geo over manually stated lat/lng if available
        test_lat = claim_record.get("stated_lat")
        test_lng = claim_record.get("stated_lng")
        for e in evidence_records:
            if e.get("exif_lat"):
                test_lat, test_lng = e.get("exif_lat"), e.get("exif_lng")
                break

        if test_lat and test_lng:
            zone_res = verify_zone_match(
                test_lat, test_lng, zone_lat, zone_lng
            )
            if zone_res["match_level"] == "outside_zone":
                geo_score = 0.0
                hold_reasons.append(
                    f"Location is too far ({
                        zone_res['distance_km']}km) from assigned zone center."
                )
            elif zone_res["match_level"] == "near_zone_boundary":
                geo_score -= 0.2
                hold_reasons.append(f"Location is at edge of zone ({
                        zone_res['distance_km']}km).")

    # 3. Timestamp Consistency Check
    # If photo claims to be now, but EXIF timestamp is wildly off
    for e in evidence_records:
        exif_ts = e.get("exif_timestamp")
        if exif_ts:
            # EXIF timestamp usually formatted as "YYYY:MM:DD HH:MM:SS"
            try:
                # Basic parsing attempt
                dt_str = exif_ts.replace(":", "-", 2)
                exif_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                # Ensure it wasn't taken weeks ago
                delta_days = (datetime.now() - exif_dt).days
                if delta_days > 3:
                    hold_reasons.append(
                        f"Photo EXIF timestamp is {delta_days} days old."
                    )
                    geo_score = float(geo_score) - 0.4
            except Exception:
                pass

    # Ensure geo score doesn't drop below 0
    geo_score = max(0.0, float(geo_score))

    review_status = (
        "hold" if len(hold_reasons) > 0 else "proceed_to_fraud_check"
    )

    return {
        "evidence_completeness_score": round(float(compl_score), 2),
        "geo_confidence_score": round(float(geo_score), 2),
        "manual_verification_status": review_status,
        "hold_reasons": hold_reasons,
    }
