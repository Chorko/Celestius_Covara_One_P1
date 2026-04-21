"""
Tests for image forensics and AI-generated evidence detection.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.image_forensics import (  # noqa: E402
    analyze_evidence_integrity,
    check_ai_generation,
)


class TestImageForensicsAI:

    def test_check_ai_generation_detects_c2pa_content_credentials(self):
        file_bytes = b"\xff\xd8\xff c2pa assertionStore content credentials"

        result = check_ai_generation(exif_metadata={}, file_bytes=file_bytes)

        assert result["c2pa_metadata_found"] is True
        assert result["ai_generated_probability"] >= 0.9
        assert "c2pa_content_credentials" in result["ai_artifacts_found"]

    def test_analyze_evidence_integrity_surfaces_ai_forensics_flags(self, monkeypatch):
        def _fake_ai_generation(*_args, **_kwargs):
            return {
                "ai_generated_probability": 0.96,
                "synthid_detected": True,
                "c2pa_metadata_found": True,
                "camera_sensor_present": False,
                "ai_artifacts_found": ["synthid_marker"],
                "detection_model": "gemini-2.0-flash",
                "risk_level": "high",
            }

        monkeypatch.setattr(
            "backend.app.services.image_forensics.check_ai_generation",
            _fake_ai_generation,
        )

        result = analyze_evidence_integrity(
            exif_metadata={
                "camera_make": "Apple",
                "camera_model": "iPhone 15",
                "software": "iOS",
                "exif_timestamp": "2026:04:20 09:30:00",
                "datetime_digitized": "2026:04:20 09:30:01",
                "modify_date": "2026:04:20 09:30:02",
                "exif_lat": 12.9716,
                "exif_lng": 77.5946,
            },
            file_bytes=b"mock-bytes",
            worker_context={
                "registered_device_make": "Apple",
                "registered_device_model": "iPhone 15",
            },
        )

        assert "ai_generation" in result["checks"]
        assert result["checks"]["ai_generation"]["synthid_detected"] is True
        assert "synthid_detected" in result["flags"]
        assert "c2pa_content_credentials_detected" in result["flags"]
        assert "ai_generated_image_high_confidence" in result["flags"]
