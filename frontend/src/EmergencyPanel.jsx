import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { createBaseMap, serviceIcon, accidentIcon, serviceTooltip } from "./mapUtils";
import { sendAlert, getServices } from "./api";
import "./emergency.css";

export default function EmergencyPanel({ jobId, emergency, result, initialAlert }) {
  const mapEl = useRef(null);
  const [services, setServices] = useState(null);
  const [alert, setAlert] = useState(initialAlert || null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [note, setNote] = useState("");
  useEffect(() => {
    getServices().then(setServices).catch(() => setServices(null));
  }, []);
  const flagged = !!result?.accident_detected;
  const { location, hospitals = [], police = [], emergency_numbers: nums = {} } = emergency || {};
  const nearestIds = new Set([...hospitals, ...police].map((s) => s.id));
  useEffect(() => {
    if (!location) return;
    const map = createBaseMap(mapEl.current, { zoom: 13 });
    const acc = [location.lat, location.lon];
    (services?.services || [])
      .filter((s) => !nearestIds.has(s.id))
      .forEach((s) => {
        L.marker([s.lat, s.lon], { icon: serviceIcon(s.type), opacity: 0.45, keyboard: false })
          .bindTooltip(serviceTooltip(s))
          .addTo(map);
      });
    const pts = [acc];
    [...hospitals, ...police].forEach((s, i) => {
      const isTop = (s.type === "hospital" && s.id === hospitals[0]?.id) ||
                    (s.type === "police" && s.id === police[0]?.id);
      L.polyline([acc, [s.lat, s.lon]], {
        color: s.type === "hospital" ? "#3dd68c" : "#4f8cff",
        weight: isTop ? 3 : 1.5,
        opacity: isTop ? 0.9 : 0.45,
        dashArray: isTop ? null : "5 6",
      }).addTo(map);
      L.marker([s.lat, s.lon], { icon: serviceIcon(s.type, { highlight: isTop }), zIndexOffset: 500 + i })
        .bindTooltip(serviceTooltip(s))
        .addTo(map);
      pts.push([s.lat, s.lon]);
    });
    L.marker(acc, { icon: accidentIcon(), zIndexOffset: 1000 })
      .bindTooltip(`<strong>Camera / accident location</strong><br/>${location.lat.toFixed(5)}, ${location.lon.toFixed(5)}`)
      .addTo(map);
    map.fitBounds(L.latLngBounds(pts), { padding: [36, 36], maxZoom: 15, animate: false });
    return () => { map.stop(); map.off(); map.remove(); };
  }, [location?.lat, location?.lon, services]);

  async function dispatch(manualOverride) {
    if (manualOverride && !window.confirm(
      "The model did NOT flag an accident in this clip. Send an alert anyway?",
    )) return;
    setSending(true);
    setError(null);
    try {
      const rec = await sendAlert(jobId, { manualOverride, note });
      setAlert(rec);
    } catch (e) {
      setError(e.message || "Could not send the alert.");
    } finally {
      setSending(false);
    }
  }
  if (!emergency) return null;
  return (
    <div className={`panel em-panel ${flagged ? "em-flagged" : ""}`}>
      <div className="em-head">
        <div>
          <h3>Emergency response</h3>
          <p className="loc-sub">
            Nearest services to {location.lat.toFixed(5)}, {location.lon.toFixed(5)} (straight-line distance, ETA at ~25 km/h).
          </p>
        </div>
        <span className="sim-badge">Simulated alerts &middot; dummy data</span>
      </div>
      <div className="em-grid">
        <div className="em-map" ref={mapEl} />
        <div className="em-side">
          <ServiceList title="Nearest hospitals" items={hospitals} type="hospital" />
          <ServiceList title="Nearest police stations" items={police} type="police" />
          <div className="em-numbers">
            Ambulance <strong>{nums.ambulance}</strong> &middot; Police <strong>{nums.police}</strong> &middot; Emergency <strong>{nums.unified_emergency}</strong>
          </div>
        </div>
      </div>
      {!alert && (
        <div className="em-actions">
          {flagged ? (
            <p className="em-prompt">
              The model flagged a possible accident ({(result.confidence * 100).toFixed(0)}% confidence).
              Review the video, then send the alert to <strong>{hospitals[0]?.name}</strong> and <strong>{police[0]?.name}</strong>.
            </p>
          ) : (
            <p className="em-prompt em-prompt-muted">
              No accident was flagged, so no alert is needed. If you can see one in the video, you can still send it manually.
            </p>
          )}
          <textarea
            className="em-note"
            placeholder="Optional note for responders (e.g. two cars, one person on the road)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
          />
          <div className="em-btn-row">
            {flagged ? (
              <button className="dispatch-btn" disabled={sending} onClick={() => dispatch(false)}>
                {sending ? "Sending…" : "Dispatch alert"}
              </button>
            ) : (
              <button className="dispatch-btn dispatch-btn-ghost" disabled={sending} onClick={() => dispatch(true)}>
                {sending ? "Sending…" : "Send manual alert"}
              </button>
            )}
          </div>
          {error && <p className="error-text em-error">{error}</p>}
        </div>
      )}
      {alert && (
        <div className="em-sent">
          <div className="em-sent-head">
            <span className="em-sent-tick">✓</span>
            <div>
              <strong>Alert sent</strong> {alert.manual_override ? "(manual override)" : ""}
              <div className="em-sent-meta">
                {new Date(alert.sent_at).toLocaleString()} &middot; ID {alert.alert_id} &middot; logged to outputs/alerts_log.jsonl
              </div>
            </div>
          </div>
          {alert.notified.map((n) => (
            <div className="em-msg" key={n.service_id}>
              <div className="em-msg-to">
                <span className={`cg-pin cg-pin-${n.type} legend-pin`}>{n.type === "hospital" ? "H" : "P"}</span>
                {n.name} &middot; {n.phone} &middot; {n.distance_km} km
                <span className="em-msg-status">{n.status}</span>
              </div>
              <p className="em-msg-body">{n.message}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ServiceList({ title, items, type }) {
  return (
    <div className="svc-list">
      <h4>{title}</h4>
      {items.map((s, i) => (
        <div className={`svc-row ${i === 0 ? "svc-row-top" : ""}`} key={s.id}>
          <span className={`cg-pin cg-pin-${type} legend-pin`}>{type === "hospital" ? "H" : "P"}</span>
          <div className="svc-main">
            <div className="svc-name">
              {s.name}
              {i === 0 && <span className="svc-tag">will be alerted</span>}
              {s.trauma_center && <span className="svc-tag svc-tag-alt">trauma</span>}
            </div>
            <div className="svc-meta">{s.area} &middot; {s.phone}</div>
          </div>
          <div className="svc-dist">
            <strong>{s.distance_km} km</strong>
            <span>~{s.eta_min} min</span>
          </div>
        </div>
      ))}
    </div>
  );
}
