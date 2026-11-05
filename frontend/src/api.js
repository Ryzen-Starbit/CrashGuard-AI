const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function errorFrom(res, fallback) {
  const body = await res.json().catch(() => null);
  if (typeof body?.detail === "string") return new Error(body.detail);
  return new Error(`${fallback}: ${res.status}`);
}

export async function uploadVideo(file, location) {
  const form = new FormData();
  form.append("file", file);
  form.append("lat", String(location.lat));
  form.append("lon", String(location.lon));
  const res = await fetch(`${API_BASE}/api/analyze`, { method: "POST", body: form });
  if (!res.ok) throw await errorFrom(res, "Upload failed");
  return res.json(); 
}

export async function getStatus(jobId) {
  const res = await fetch(`${API_BASE}/api/status/${jobId}`);
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
  return res.json();
}

export function videoUrl(jobId) {
  return `${API_BASE}/api/video/${jobId}`;
}

export async function getServices() {
  const res = await fetch(`${API_BASE}/api/services`);
  if (!res.ok) throw new Error(`Could not load services: ${res.status}`);
  return res.json(); 
}

export async function sendAlert(jobId, { manualOverride = false, note = "" } = {}) {
  const res = await fetch(`${API_BASE}/api/alert/${jobId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ manual_override: manualOverride, operator_note: note }),
  });
  if (!res.ok) throw await errorFrom(res, "Alert failed");
  return res.json();
}
