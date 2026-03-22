"""
DEVTrails — Evidence Processing Service

Handles extraction of EXIF metadata (geo-location, timestamp, camera info,
software, modification dates) from uploaded evidence photos.

Extended to support image forensics: extracts DateTimeDigitized, ModifyDate,
Software, Make, LensModel, FocalLength, ExposureTime, ISOSpeedRatings,
and EXIF thumbnail for the image_forensics service.
"""

from io import BytesIO
from PIL import Image, ExifTags

# Full set of EXIF tags we extract for forensics
FORENSIC_TAGS = {
    "DateTimeOriginal": "exif_timestamp",
    "DateTimeDigitized": "datetime_digitized",
    "DateTime": "modify_date",
    "Model": "camera_model",
    "Make": "camera_make",
    "Software": "software",
    "LensModel": "lens_model",
    "FocalLength": "focal_length",
    "ExposureTime": "exposure_time",
    "ISOSpeedRatings": "iso",
}


def extract_exif_metadata(file_bytes: bytes) -> dict:
    """
    Extracts timestamp, GPS coordinates, camera info, and forensic-relevant
    EXIF fields from image bytes.

    Returns a rich metadata dict for downstream use by:
    - manual_claim_verifier.py (evidence checks)
    - anti_spoofing.py (EXIF vs browser GPS)
    - image_forensics.py (integrity analysis)
    """
    metadata = {
        "exif_timestamp": None,
        "datetime_digitized": None,
        "modify_date": None,
        "exif_lat": None,
        "exif_lng": None,
        "camera_model": None,
        "camera_make": None,
        "software": None,
        "lens_model": None,
        "focal_length": None,
        "exposure_time": None,
        "iso": None,
        "has_thumbnail": False,
        "gps_decimal_places": None,
        "exif_field_count": 0,
    }

    try:
        img = Image.open(BytesIO(file_bytes))
        exif_data = img._getexif()  # type: ignore

        if not exif_data:
            return metadata

        # Helper to convert EXIF GPS degrees to decimal
        def get_decimal_from_dms(dms, ref):
            degrees = dms[0]
            minutes = dms[1]
            seconds = dms[2]

            decimal = (
                float(degrees) + float(minutes) / 60 + float(seconds) / 3600
            )
            if ref in ["S", "W"]:
                decimal = -decimal
            return round(decimal, 6)

        gps_info = None
        field_count = 0

        for tag_id, value in exif_data.items():
            tag = ExifTags.TAGS.get(tag_id, str(tag_id))

            # Map known forensic tags
            if tag in FORENSIC_TAGS:
                key = FORENSIC_TAGS[tag]
                metadata[key] = str(value) if value is not None else None  # type: ignore
                field_count += 1

            if tag == "GPSInfo":
                gps_info = value

        metadata["exif_field_count"] = field_count

        # Extract GPS coordinates
        if gps_info:
            gps_tags = {}
            for t in gps_info:
                g_tag = ExifTags.GPSTAGS.get(t, t)
                gps_tags[g_tag] = gps_info[t]

            if (
                "GPSLatitude" in gps_tags
                and "GPSLatitudeRef" in gps_tags
                and "GPSLongitude" in gps_tags
                and "GPSLongitudeRef" in gps_tags
            ):
                try:
                    lat = get_decimal_from_dms(
                        gps_tags["GPSLatitude"], gps_tags["GPSLatitudeRef"]
                    )
                    lng = get_decimal_from_dms(
                        gps_tags["GPSLongitude"], gps_tags["GPSLongitudeRef"]
                    )
                    metadata["exif_lat"] = lat
                    metadata["exif_lng"] = lng

                    # GPS precision analysis: count decimal places
                    lat_str = f"{lat:.10f}".rstrip("0")
                    lng_str = f"{lng:.10f}".rstrip("0")
                    lat_decimals = (
                        len(lat_str.split(".")[-1]) if "." in lat_str else 0
                    )
                    lng_decimals = (
                        len(lng_str.split(".")[-1]) if "." in lng_str else 0
                    )
                    metadata["gps_decimal_places"] = min(
                        lat_decimals, lng_decimals
                    )
                except Exception:
                    pass

        # Check for embedded thumbnail
        try:
            if hasattr(img, "_getexif") and exif_data:
                # EXIF tag 513 = JPEGThumbnailOffset (thumbnail presence
                # indicator)
                if 513 in exif_data or 514 in exif_data:
                    metadata["has_thumbnail"] = True
        except Exception:
            pass

    except Exception as e:
        print(f"EXIF extraction error: {e}")

    return metadata
