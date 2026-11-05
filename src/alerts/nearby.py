import json
import math
from functools import lru_cache
from pathlib import Path

SERVICES_PATH = Path(__file__).resolve().parents[2] / "data" / "pune_services.json"

EARTH_RADIUS_KM = 6371.0
AVG_CITY_SPEED_KMPH = 25.0 

@lru_cache(maxsize=1)
def load_services(path: str = str(SERVICES_PATH)) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))

def validate_location(lat: float, lon: float) -> str | None:
    if lat is None or lon is None:
        return "Location is required."
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return "Latitude must be between -90 and 90 and longitude between -180 and 180."
    b = load_services()["bounds"]
    if not (b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]):
        return (f"Location ({lat:.4f}, {lon:.4f}) is outside the Pune demo area "
                f"(lat {b['min_lat']}-{b['max_lat']}, lon {b['min_lon']}-{b['max_lon']}).")
    return None

def find_nearest(lat: float, lon: float, n_hospitals: int = 3, n_police: int = 2) -> dict:
    data = load_services()
    ranked = []
    for s in data["services"]:
        d = haversine_km(lat, lon, s["lat"], s["lon"])
        ranked.append({
            **s,
            "distance_km": round(d, 2),
            "eta_min": max(1, round(d / AVG_CITY_SPEED_KMPH * 60)),
        })
    ranked.sort(key=lambda s: s["distance_km"])
    hospitals = [s for s in ranked if s["type"] == "hospital"][:n_hospitals]
    police = [s for s in ranked if s["type"] == "police"][:n_police]
    return {
        "location": {"lat": lat, "lon": lon},
        "hospitals": hospitals,
        "police": police,
        "emergency_numbers": data["emergency_numbers"],
    }

if __name__ == "__main__":
    import pprint
    pprint.pprint(find_nearest(18.5018, 73.8636))  
