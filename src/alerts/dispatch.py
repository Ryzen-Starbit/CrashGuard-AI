import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[2] / "outputs" / "alerts_log.jsonl"

def build_message(verdict: dict, location: dict, service: dict) -> str:
    lat, lon = location["lat"], location["lon"]
    maps_link = f"https://www.google.com/maps?q={lat},{lon}"
    reasons = "; ".join(verdict.get("explanation", [])[:3])
    return (
        f"[CrashGuard AI] Possible road accident near {lat:.5f}, {lon:.5f}. "
        f"Confidence {verdict.get('confidence', 0):.0%} at ~{verdict.get('event_time_s', '?')}s of CCTV clip. "
        f"Signals: {reasons}. "
        f"You are {service['distance_km']} km away (~{service['eta_min']} min). "
        f"Location: {maps_link}"
    )

def send_message(service: dict, text: str) -> dict:
    print(f"[SIMULATED ALERT] -> {service['name']} ({service['phone']}): {text}")
    return {
        "service_id": service["id"],
        "name": service["name"],
        "type": service["type"],
        "phone": service["phone"],
        "distance_km": service["distance_km"],
        "eta_min": service["eta_min"],
        "channel": "simulated-sms",
        "status": "delivered",
        "message": text,
    }

def dispatch_alert(job_id: str, clip_name: str, verdict: dict, emergency: dict,
                   manual_override: bool = False, operator_note: str = "") -> dict:
    location = emergency["location"]
    targets = []
    if emergency.get("hospitals"):
        targets.append(emergency["hospitals"][0])
    if emergency.get("police"):
        targets.append(emergency["police"][0])
    notified = [send_message(s, build_message(verdict, location, s)) for s in targets]
    record = {
        "alert_id": uuid.uuid4().hex[:10],
        "job_id": job_id,
        "clip": clip_name,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "location": location,
        "confidence": verdict.get("confidence"),
        "event_time_s": verdict.get("event_time_s"),
        "model_flagged_accident": bool(verdict.get("accident_detected")),
        "manual_override": manual_override,
        "operator_note": operator_note,
        "notified": notified,
        "simulated": True,
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record

def read_alert_log(limit: int = 50) -> list:
    if not LOG_PATH.exists():
        return []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return list(reversed(rows))[:limit]
