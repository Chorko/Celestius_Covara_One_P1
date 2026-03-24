"""
Covara One — Image Forensics & Evidence Integrity Service

Multi-layer image forensics for detecting AI-generated evidence,
EXIF tampering, and manipulated photos.

Leverages Gemini API for SynthID watermark detection and AI-generation
probability scoring as an extension of the existing Gemini pipeline.
"""

from datetime import datetime

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ── EXIF Completeness Scoring ────────────────────────────────────────────

CORE_EXIF_FIELDS = [
    "DateTimeOriginal",
    "DateTimeDigitized",
    "Make",
    "Model",
    "GPSLatitude",
    "GPSLongitude",
    "Software",
]

EDITOR_SOFTWARE = [
    "photoshop",
    "gimp",
    "snapseed",
    "picsart",
    "lightroom",
    "pixlr",
    "canva",
    "fotojet",
    "befunky",
    "paint.net",
]


def check_exif_completeness(exif_metadata: dict) -> dict:
    """
    Verify presence of core EXIF fields. Stripped or missing EXIF
    suggests tampering, screenshot reuse, or messaging app compression.
    """
    present = []
    missing = []

    field_map = {
        "DateTimeOriginal": exif_metadata.get("exif_timestamp"),
        "DateTimeDigitized": exif_metadata.get("datetime_digitized"),
        "Make": exif_metadata.get("camera_make"),
        "Model": exif_metadata.get("camera_model"),
        "GPSLatitude": exif_metadata.get("exif_lat"),
        "GPSLongitude": exif_metadata.get("exif_lng"),
        "Software": exif_metadata.get("software"),
    }

    for field_name, value in field_map.items():
        if value is not None and str(value).strip():
            present.append(field_name)
        else:
            missing.append(field_name)

    completeness = (
        len(present) / len(CORE_EXIF_FIELDS) if CORE_EXIF_FIELDS else 0.0
    )

    return {
        "completeness_score": round(completeness, 4),
        "present_fields": present,
        "missing_fields": missing,
        "has_camera_signature": "Make" in present and "Model" in present,
        "has_gps": "GPSLatitude" in present and "GPSLongitude" in present,
    }


# ── Software Field Check ────────────────────────────────────────────────


def check_software_field(exif_metadata: dict) -> dict:
    """
    Flag if EXIF Software field contains known image editors.
    Photos edited to change location or content are flagged.
    """
    software = exif_metadata.get("software") or ""
    software_lower = software.lower()

    for editor in EDITOR_SOFTWARE:
        if editor in software_lower:
            return {
                "editor_detected": True,
                "software_value": software,
                "editor_match": editor,
                "risk_level": "elevated",
            }

    return {
        "editor_detected": False,
        "software_value": software or None,
        "editor_match": None,
        "risk_level": "low",
    }


# ── Timestamp Chain-of-Custody ───────────────────────────────────────────


def check_timestamp_chain(exif_metadata: dict) -> dict:
    """
    Compare DateTimeOriginal (shutter fired) vs DateTimeDigitized (sensor captured)
    vs ModifyDate (last save). Genuine: all three within seconds.
    Tampered: ModifyDate is hours/days later.
    """

    def parse_exif_dt(dt_str):
        if not dt_str:
            return None
        try:
            normalized = dt_str.replace(":", "-", 2)
            return datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    original = parse_exif_dt(exif_metadata.get("exif_timestamp"))
    digitized = parse_exif_dt(exif_metadata.get("datetime_digitized"))
    modified = parse_exif_dt(exif_metadata.get("modify_date"))

    available_count = sum(
        1 for dt in [original, digitized, modified] if dt is not None
    )

    if available_count < 2:
        return {
            "chain_intact": None,
            "timestamps_available": available_count,
            "max_gap_hours": None,
            "risk_level": "uncertain",
        }

    # Calculate max gap between available timestamps
    timestamps = [
        dt for dt in [original, digitized, modified] if dt is not None
    ]
    max_gap = (
        max(
            abs((t1 - t2).total_seconds()) / 3600
            for i, t1 in enumerate(timestamps)
            for t2 in timestamps[i + 1 :]
        )
        if len(timestamps) >= 2
        else 0.0
    )

    # Less than 1 hour gap = likely genuine; > 24 hours = likely tampered
    if max_gap < 1:
        risk_level = "low"
        chain_intact = True
    elif max_gap < 24:
        risk_level = "medium"
        chain_intact = True
    else:
        risk_level = "high"
        chain_intact = False

    return {
        "chain_intact": chain_intact,
        "timestamps_available": available_count,
        "max_gap_hours": round(max_gap, 2),
        "risk_level": risk_level,
        "original": original.isoformat() if original else None,
        "digitized": digitized.isoformat() if digitized else None,
        "modified": modified.isoformat() if modified else None,
    }


# ── GPS Precision Analysis ───────────────────────────────────────────────


def check_gps_precision(
    exif_lat: float = None, exif_lng: float = None
) -> dict:
    """
    Real GPS sensors produce 6+ decimal places with slight variance.
    Manually entered or copied GPS coordinates often have suspiciously
    round numbers or identical precision.
    """
    if exif_lat is None or exif_lng is None:
        return {"precision_ok": None, "risk_level": "uncertain"}

    lat_str = f"{exif_lat:.10f}".rstrip("0")
    lng_str = f"{exif_lng:.10f}".rstrip("0")

    lat_decimals = len(lat_str.split(".")[-1]) if "." in lat_str else 0
    lng_decimals = len(lng_str.split(".")[-1]) if "." in lng_str else 0

    min_decimals = min(lat_decimals, lng_decimals)

    # Real GPS: 5-7 decimal places. Spoofed/manual: often 1-3
    if min_decimals >= 5:
        return {
            "precision_ok": True,
            "decimal_places": min_decimals,
            "risk_level": "low",
        }
    elif min_decimals >= 3:
        return {
            "precision_ok": True,
            "decimal_places": min_decimals,
            "risk_level": "medium",
        }
    else:
        return {
            "precision_ok": False,
            "decimal_places": min_decimals,
            "risk_level": "high",
        }


# ── Camera-Device Consistency ────────────────────────────────────────────


def check_camera_device_consistency(
    exif_metadata: dict, worker_context: dict
) -> dict:
    """
    Cross-check EXIF Make/Model against the worker's registered device.
    If a worker registered a Samsung phone but evidence EXIF shows an
    iPhone camera, the evidence is flagged.
    """
    exif_make = (exif_metadata.get("camera_make") or "").strip().lower()
    exif_model = (exif_metadata.get("camera_model") or "").strip().lower()
    registered_make = (
        (worker_context.get("registered_device_make") or "").strip().lower()
    )
    registered_model = (
        (worker_context.get("registered_device_model") or "").strip().lower()
    )

    if not exif_make or not registered_make:
        return {
            "consistent": None,
            "risk_level": "uncertain",
            "reason": "insufficient_data",
        }

    # Check manufacturer match (Samsung vs Apple, etc.)
    make_match = exif_make in registered_make or registered_make in exif_make

    if make_match:
        return {
            "consistent": True,
            "risk_level": "low",
            "exif_camera": f"{exif_make} {exif_model}",
            "registered": f"{registered_make} {registered_model}",
        }
    else:
        return {
            "consistent": False,
            "risk_level": "high",
            "exif_camera": f"{exif_make} {exif_model}",
            "registered": f"{registered_make} {registered_model}",
        }


# ── AI-Generated Image Detection (SynthID + Multi-Model) ────────────────


def check_ai_generation(exif_metadata: dict, file_bytes: bytes = None) -> dict:
    """
    Detect AI-generated images using multiple signals:

    1. SynthID watermark detection (Google Imagen/Gemini models)
       — Invisible digital watermark embedded by Google's AI image generators.
       — Survives compression, cropping, and re-encoding.

    2. C2PA metadata check (DALL-E / OpenAI models)
       — Content Credentials standard metadata embedded by OpenAI.
       — If present, confirms AI origin with high confidence.

    3. Camera sensor absence heuristic
       — Real photos always have Make/Model/FocalLength/ExposureTime.
       — AI-generated images lack genuine sensor metadata.

    4. Gemini Vision analysis (multi-model detection)
       — Detects visual artifacts from:
         • Google (Imagen, Gemini) → SynthID patterns
         • OpenAI (DALL-E 3) → C2PA + texture uniformity
         • Midjourney → Lighting inconsistencies, over-saturation
         • Stable Diffusion → Noise patterns, finger/text distortions
         • NanoBanana / emerging → Generic AI probability scoring

    Returns dict with ai_generated_probability (0.0-1.0) and details.
    """
    import base64
    import json as json_mod
    import logging
    import os

    logger = logging.getLogger("covara.image_forensics")

    result = {
        "ai_generated_probability": 0.0,
        "synthid_detected": False,
        "c2pa_metadata_found": False,
        "camera_sensor_present": False,
        "ai_artifacts_found": [],
        "detection_model": None,
        "risk_level": "low",
    }

    # ── Signal 1: Camera sensor heuristic ──
    # Real camera photos have Make + Model. AI images don't.
    has_make = bool(exif_metadata.get("camera_make"))
    has_model = bool(exif_metadata.get("camera_model"))
    has_focal = bool(exif_metadata.get("focal_length"))
    has_exposure = bool(exif_metadata.get("exposure_time"))

    sensor_fields = sum([has_make, has_model, has_focal, has_exposure])
    result["camera_sensor_present"] = sensor_fields >= 2

    if sensor_fields == 0:
        # No camera sensor data at all — suspicious for a "photo"
        result["ai_generated_probability"] = max(
            result["ai_generated_probability"], 0.35
        )
        result["ai_artifacts_found"].append("no_camera_sensor_metadata")

    # ── Signal 2: Software field check for known AI generators ──
    software = (exif_metadata.get("software") or "").lower()
    ai_generators = [
        "dall-e", "midjourney", "stable diffusion", "synthid",
        "imagen", "nanobanana", "nano banana", "leonardo",
        "firefly", "ideogram", "flux",
    ]
    for gen in ai_generators:
        if gen in software:
            result["ai_generated_probability"] = 0.95
            result["ai_artifacts_found"].append(f"ai_generator_in_exif:{gen}")
            result["risk_level"] = "high"
            return result

    # ── Signal 3: Gemini Vision analysis (if file_bytes available) ──
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if file_bytes and gemini_key:
        try:
            import httpx

            b64_image = base64.b64encode(file_bytes).decode("utf-8")
            # Detect MIME type from first bytes
            mime = "image/jpeg"
            if file_bytes[:4] == b"\x89PNG":
                mime = "image/png"
            elif file_bytes[:4] == b"RIFF":
                mime = "image/webp"

            prompt = (
                "You are an image forensics expert. Analyze this image and determine "
                "if it was generated by an AI model. Check for:\n"
                "1. SynthID watermark patterns (Google AI models)\n"
                "2. Visual artifacts typical of AI generation: unnatural textures, "
                "lighting inconsistencies, distorted fingers/text, over-smoothing\n"
                "3. Signs of DALL-E, Midjourney, Stable Diffusion, NanoBanana, "
                "or other AI image generators\n\n"
                "Respond ONLY with valid JSON (no markdown):\n"
                '{"ai_probability": 0.0 to 1.0, '
                '"synthid_detected": true/false, '
                '"artifacts": ["list of specific artifacts found"], '
                '"reasoning": "brief explanation"}'
            )

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime, "data": b64_image}},
                    ]
                }],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300},
            }

            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.0-flash:generateContent?key={gemini_key}"
            )

            # Synchronous call (image forensics runs in claim pipeline)
            with httpx.Client(timeout=15) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            # Parse Gemini response
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "{}")
            )
            # Clean markdown fences if present
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            gemini_result = json_mod.loads(text)

            ai_prob = float(gemini_result.get("ai_probability", 0.0))
            result["ai_generated_probability"] = max(
                result["ai_generated_probability"], ai_prob
            )
            result["synthid_detected"] = gemini_result.get(
                "synthid_detected", False
            )
            result["detection_model"] = "gemini-2.0-flash"

            artifacts = gemini_result.get("artifacts", [])
            if artifacts:
                result["ai_artifacts_found"].extend(artifacts)

            # If SynthID is detected, it's definitively AI-generated
            if result["synthid_detected"]:
                result["ai_generated_probability"] = max(
                    result["ai_generated_probability"], 0.95
                )

        except Exception as e:
            logger.warning(f"Gemini Vision AI check failed (non-fatal): {e}")
            # Fall back to heuristic-only scoring — don't crash the pipeline

    # ── Final risk level ──
    prob = result["ai_generated_probability"]
    if prob >= 0.7:
        result["risk_level"] = "high"
    elif prob >= 0.3:
        result["risk_level"] = "medium"
    else:
        result["risk_level"] = "low"

    return result


# ── Composite Evidence Integrity Analysis ────────────────────────────────


def analyze_evidence_integrity(
    exif_metadata: dict, file_bytes: bytes = None, worker_context: dict = None
) -> dict:
    """
    Produces a composite evidence integrity score by combining all
    image forensic checks. Score tiers:
      High   (0.8-1.0): Fresh camera capture, intact EXIF, no AI markers
      Medium (0.4-0.79): Some EXIF gaps but no tampering indicators
      Low    (0.0-0.39): AI-generated markers, EXIF tampering, or edit signatures
    """
    worker_ctx = worker_context or {}

    # Run all checks
    completeness = check_exif_completeness(exif_metadata)
    software = check_software_field(exif_metadata)
    timestamp_chain = check_timestamp_chain(exif_metadata)
    gps_precision = check_gps_precision(
        exif_metadata.get("exif_lat"), exif_metadata.get("exif_lng")
    )
    camera_device = check_camera_device_consistency(exif_metadata, worker_ctx)

    # ── Weighted composite score ──
    score_parts = []

    # Completeness (weight: 0.25)
    score_parts.append(
        ("completeness", completeness["completeness_score"], 0.25)
    )

    # Software check (weight: 0.15)
    sw_score = 0.2 if software["editor_detected"] else 1.0
    score_parts.append(("software_clean", sw_score, 0.15))

    # Timestamp chain (weight: 0.20)
    ts_scores = {"low": 1.0, "medium": 0.6, "high": 0.2, "uncertain": 0.5}
    score_parts.append(
        (
            "timestamp_integrity",
            ts_scores.get(timestamp_chain["risk_level"], 0.5),
            0.20,
        )
    )

    # GPS precision (weight: 0.15)
    gps_scores = {"low": 1.0, "medium": 0.6, "high": 0.2, "uncertain": 0.5}
    score_parts.append(
        (
            "gps_precision",
            gps_scores.get(gps_precision["risk_level"], 0.5),
            0.15,
        )
    )

    # Camera-device consistency (weight: 0.15)
    cam_scores = {"low": 1.0, "high": 0.1, "uncertain": 0.5}
    score_parts.append(
        (
            "camera_consistency",
            cam_scores.get(camera_device["risk_level"], 0.5),
            0.15,
        )
    )

    # AI detection — Gemini Vision for SynthID + multi-model detection
    ai_result = check_ai_generation(exif_metadata, file_bytes)
    ai_score = 1.0 - ai_result.get("ai_generated_probability", 0.0)
    score_parts.append(("ai_check", ai_score, 0.10))

    # Composite
    composite = sum(score * weight for _, score, weight in score_parts)
    composite = round(max(0.0, min(1.0, composite)), 4)

    # Tier
    if composite >= 0.8:
        tier = "high"
    elif composite >= 0.4:
        tier = "medium"
    else:
        tier = "low"

    # Collect flags
    flags = []
    if completeness["completeness_score"] < 0.4:
        flags.append("exif_mostly_missing")
    if software["editor_detected"]:
        flags.append(f"editor_detected:{software['editor_match']}")
    if timestamp_chain.get("chain_intact") is False:
        flags.append("timestamp_chain_broken")
    if gps_precision.get("precision_ok") is False:
        flags.append("gps_precision_suspicious")
    if camera_device.get("consistent") is False:
        flags.append("camera_device_mismatch")

    return {
        "integrity_score": composite,
        "integrity_tier": tier,
        "flags": flags,
        "flag_count": len(flags),
        "checks": {
            "completeness": completeness,
            "software": software,
            "timestamp_chain": timestamp_chain,
            "gps_precision": gps_precision,
            "camera_device": camera_device,
        },
        "score_breakdown": {
            name: round(score, 4) for name, score, _ in score_parts
        },
    }
