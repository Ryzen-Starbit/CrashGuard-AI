import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import {
  createBaseMap, drawBounds, serviceIcon, accidentIcon, serviceTooltip,
  inBounds, DEFAULT_BOUNDS,
} from "./mapUtils";
import "./emergency.css";

const PRESETS = [
  { label: "Swargate", lat: 18.5018, lon: 73.8636 },
  { label: "Katraj", lat: 18.4575, lon: 73.8677 },
  { label: "Hinjewadi", lat: 18.5913, lon: 73.7389 },
  { label: "Hadapsar", lat: 18.5089, lon: 73.926 },
  { label: "Shivajinagar", lat: 18.5308, lon: 73.8475 },
];

export default function LocationPicker({ value, onChange, services }) {
  const mapEl = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const selectRef = useRef(null);
  const bounds = services?.bounds || DEFAULT_BOUNDS;
  const [latText, setLatText] = useState(value ? String(value.lat) : "");
  const [lonText, setLonText] = useState(value ? String(value.lon) : "");
  const [inputError, setInputError] = useState(null);

  function select(loc) {
    setLatText(String(loc.lat));
    setLonText(String(loc.lon));
    setInputError(null);
    onChange(loc);
  }
  useEffect(() => { selectRef.current = select; });
  useEffect(() => {
    const map = createBaseMap(mapEl.current, { zoom: 12 });
    mapRef.current = map;
    map.on("click", (e) => {
      const lat = +e.latlng.lat.toFixed(6);
      const lon = +e.latlng.lng.toFixed(6);
      selectRef.current({ lat, lon });
    });
    return () => { map.stop(); map.off(); map.remove(); mapRef.current = null; markerRef.current = null; };
  }, []);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const layer = L.layerGroup().addTo(map);
    drawBounds(layer, bounds);
    (services?.services || []).forEach((s) => {
      L.marker([s.lat, s.lon], { icon: serviceIcon(s.type), keyboard: false })
        .bindTooltip(serviceTooltip(s))
        .addTo(layer);
    });
    return () => layer.remove();
  }, [services, bounds]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (!value) {
      markerRef.current?.remove();
      markerRef.current = null;
      return;
    }
    if (!markerRef.current) {
      markerRef.current = L.marker([value.lat, value.lon], {
        icon: accidentIcon(), draggable: true, zIndexOffset: 1000,
      }).addTo(map);
      markerRef.current.on("dragend", (e) => {
        const p = e.target.getLatLng();
        selectRef.current({ lat: +p.lat.toFixed(6), lon: +p.lng.toFixed(6) });
      });
    } else {
      markerRef.current.setLatLng([value.lat, value.lon]);
    }
  }, [value]);

  function applyTyped(e) {
    e?.preventDefault();
    let latStr = latText, lonStr = lonText;
    if (latText.includes(",") && !lonText.trim()) {
      [latStr, lonStr] = latText.split(",").map((x) => x.trim());
    }
    const lat = parseFloat(latStr);
    const lon = parseFloat(lonStr);
    if (Number.isNaN(lat) || Number.isNaN(lon)) {
      setInputError("Enter both latitude and longitude as numbers, e.g. 18.5018 and 73.8636.");
      return;
    }
    if (!inBounds(lat, lon, bounds)) {
      setInputError(
        `That point is outside the Pune demo area (lat ${bounds.min_lat}–${bounds.max_lat}, lon ${bounds.min_lon}–${bounds.max_lon}).`,
      );
      return;
    }
    select({ lat, lon });
    mapRef.current?.setView([lat, lon], 14, { animate: false });
  }

  function pickPreset(p) {
    select({ lat: p.lat, lon: p.lon });
    mapRef.current?.setView([p.lat, p.lon], 14, { animate: false });
  }

  return (
    <div className="panel loc-panel">
      <div className="loc-head">
        <div>
          <div className="loc-step">Step 1</div>
          <h3>Where is this camera?</h3>
          <p className="loc-sub">
            Click the map (or drag the pin), or type coordinates. Used to find the nearest hospital and police station.
          </p>
        </div>
        <div className={`loc-status ${value ? "loc-status-set" : ""}`}>
          {value ? `${value.lat.toFixed(5)}, ${value.lon.toFixed(5)}` : "No location yet"}
        </div>
      </div>
      <div className="loc-map" ref={mapEl} />
      <form className="loc-form" onSubmit={applyTyped}>
        <label>
          Latitude
          <input
            type="text" inputMode="decimal" placeholder="18.5018"
            value={latText} onChange={(e) => setLatText(e.target.value)}
          />
        </label>
        <label>
          Longitude
          <input
            type="text" inputMode="decimal" placeholder="73.8636"
            value={lonText} onChange={(e) => setLonText(e.target.value)}
          />
        </label>
        <button type="submit" className="loc-apply">Set location</button>
      </form>
      {inputError && <p className="error-text loc-error">{inputError}</p>}
      <div className="loc-presets">
        <span>Quick pick:</span>
        {PRESETS.map((p) => (
          <button key={p.label} type="button" className="chip-btn" onClick={() => pickPreset(p)}>
            {p.label}
          </button>
        ))}
      </div>
      <div className="map-legend">
        <span><i className="cg-pin cg-pin-hospital legend-pin">H</i> Hospital</span>
        <span><i className="cg-pin cg-pin-police legend-pin">P</i> Police station</span>
        <span><i className="legend-acc" /> Camera / accident location</span>
        <span className="legend-note">Dummy data &middot; Pune only</span>
      </div>
    </div>
  );
}
