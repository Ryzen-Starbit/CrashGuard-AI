import L from "leaflet";
import "leaflet/dist/leaflet.css";

export const PUNE_CENTER = [18.5204, 73.8567];
export const DEFAULT_BOUNDS = { min_lat: 18.4, max_lat: 18.7, min_lon: 73.7, max_lon: 74.05 };
export function inBounds(lat, lon, b = DEFAULT_BOUNDS) {
  return lat >= b.min_lat && lat <= b.max_lat && lon >= b.min_lon && lon <= b.max_lon;
}
export function createBaseMap(el, { zoom = 12 } = {}) {
  const map = L.map(el, { zoomControl: true, attributionControl: true }).setView(PUNE_CENTER, zoom);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  return map;
}
export function drawBounds(map, b = DEFAULT_BOUNDS) {
  return L.rectangle(
    [[b.min_lat, b.min_lon], [b.max_lat, b.max_lon]],
    { color: "#4f8cff", weight: 1, dashArray: "6 6", fill: false, interactive: false },
  ).addTo(map);
}
export function serviceIcon(type, { highlight = false } = {}) {
  const cls = `cg-pin cg-pin-${type}${highlight ? " cg-pin-hl" : ""}`;
  const glyph = type === "hospital" ? "H" : "P";
  const size = highlight ? 28 : 20;
  return L.divIcon({
    className: "",
    html: `<div class="${cls}">${glyph}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}
export function accidentIcon() {
  return L.divIcon({
    className: "",
    html: `<div class="cg-accident"><span class="cg-accident-ring"></span><span class="cg-accident-dot">!</span></div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });
}
export function serviceTooltip(s) {
  const dist = s.distance_km != null ? `<br/>${s.distance_km} km &middot; ~${s.eta_min} min` : "";
  return `<strong>${s.name}</strong><br/>${s.area} &middot; ${s.type === "hospital" ? "Hospital" : "Police"}${dist}`;
}
