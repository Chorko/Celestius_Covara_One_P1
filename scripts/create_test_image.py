import os
from PIL import Image
import piexif
from datetime import datetime

def create_test_evidence():
    # 1. Create a dummy green image
    img = Image.new('RGB', (800, 600), color='forestgreen')
    
    # 2. Prepare EXIF data
    # Lat/Lng: 17.3850, 78.4867 (Hyderabad) as an example.
    # We must represent this in EXIF GPS format (Rational tuples)
    
    def to_deg(value, loc):
        if value < 0:
            loc_value = loc[0]
        elif value > 0:
            loc_value = loc[1]
        else:
            loc_value = ""
        abs_value = abs(value)
        d = int(abs_value)
        m = int((abs_value - d) * 60)
        s = round(((abs_value - d) * 60 - m) * 60 * 10000)
        return ((d, 1), (m, 1), (s, 10000)), loc_value

    lat, lat_ref = to_deg(17.385044, ["S", "N"])
    lng, lng_ref = to_deg(78.486671, ["W", "E"])

    # EXIF Date format: YYYY:MM:DD HH:MM:SS
    # Assuming "now" so it passes the < 3 days check
    now_str = datetime.now().strftime("%Y:%m:%d %H:%M:%S")

    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: b"Google",
            piexif.ImageIFD.Model: b"Pixel Test Engine"
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: now_str.encode('utf-8')
        },
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: lat_ref.encode('utf-8'),
            piexif.GPSIFD.GPSLatitude: lat,
            piexif.GPSIFD.GPSLongitudeRef: lng_ref.encode('utf-8'),
            piexif.GPSIFD.GPSLongitude: lng,
        }
    }
    
    exif_bytes = piexif.dump(exif_dict)
    
    path = os.path.join(os.path.dirname(__file__), '..', 'test_evidence.jpg')
    img.save(path, format="jpeg", exif=exif_bytes)
    print(f"Created {path} with EXIF data")

if __name__ == "__main__":
    create_test_evidence()
