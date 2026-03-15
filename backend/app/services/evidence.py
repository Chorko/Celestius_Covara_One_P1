"""
DEVTrails — Evidence Processing Service

Handles extraction of EXIF metadata (geo-location, timestamp)
from uploaded evidence photos to ensure integrity and prevent spoofing.
"""

from io import BytesIO
from PIL import Image, ExifTags

def extract_exif_metadata(file_bytes: bytes) -> dict:
    """
    Extracts timestamp and GPS coordinates from image bytes if available.
    Returns:
        {
            "exif_timestamp": str or None,
            "exif_lat": float or None,
            "exif_lng": float or None,
            "camera_model": str or None
        }
    """
    metadata = {
        "exif_timestamp": None,
        "exif_lat": None,
        "exif_lng": None,
        "camera_model": None
    }
    
    try:
        img = Image.open(BytesIO(file_bytes))
        exif_data = img._getexif()
        
        if not exif_data:
            return metadata
            
        # Helper to convert EXIF GPS degrees to decimal
        def get_decimal_from_dms(dms, ref):
            degrees = dms[0]
            minutes = dms[1]
            seconds = dms[2]
            
            decimal = float(degrees) + float(minutes)/60 + float(seconds)/3600
            if ref in ['S', 'W']:
                decimal = -decimal
            return round(decimal, 6)

        gps_info = None

        for tag_id, value in exif_data.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            if tag == "DateTimeOriginal":
                metadata["exif_timestamp"] = str(value)
            elif tag == "Model":
                metadata["camera_model"] = str(value)
            elif tag == "GPSInfo":
                gps_info = value
                
        if gps_info:
            gps_tags = {}
            for t in gps_info:
                g_tag = ExifTags.GPSTAGS.get(t, t)
                gps_tags[g_tag] = gps_info[t]
                
            if "GPSLatitude" in gps_tags and "GPSLatitudeRef" in gps_tags and \
               "GPSLongitude" in gps_tags and "GPSLongitudeRef" in gps_tags:
                try:
                    metadata["exif_lat"] = get_decimal_from_dms(gps_tags["GPSLatitude"], gps_tags["GPSLatitudeRef"])
                    metadata["exif_lng"] = get_decimal_from_dms(gps_tags["GPSLongitude"], gps_tags["GPSLongitudeRef"])
                except Exception:
                    pass

    except Exception as e:
        print(f"EXIF extraction error: {e}")
        
    return metadata
