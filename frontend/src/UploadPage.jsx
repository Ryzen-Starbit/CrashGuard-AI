import { useEffect, useRef, useState } from "react";
import { uploadVideo, getServices } from "./api";
import LocationPicker from "./LocationPicker";

const MAX_UPLOAD_MB = 100;

const STEPS = [
  { title: "Detect & track", body: "YOLOv8 finds and tracks every vehicle in the footage, frame by frame." },
  { title: "Extract signals", body: "Overlap, braking, and bounding-box deformation are measured for every moment." },
  { title: "Score windows", body: "A trained classifier scores every half-second window of the clip." },
  { title: "Flag the peak", body: "The clip's most anomalous moment is checked against its own baseline." },
  { title: "Alert responders", body: "The nearest hospital and police station are found from the camera location and alerted after review." },
];

export default function UploadPage({ onJobStarted }) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [location, setLocation] = useState(null);
  const [services, setServices] = useState(null);
  const inputRef = useRef(null);
  useEffect(() => {
    getServices()
      .then(setServices)
      .catch(() => setError("Could not load hospital / police data. Is the backend running?"));
  }, []);
  async function handleFile(file) {
    if (!file) return;
    if (!location) {
      setError("Set the camera location on the map first (Step 1).");
      return;
    }
    if (!file.type.startsWith("video/")) {
      setError("Please choose a video file (.mp4, .mov, .avi...).");
      return;
    }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setError(`This video is larger than ${MAX_UPLOAD_MB} MB. Trim it or pick a shorter clip.`);
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const { job_id } = await uploadVideo(file, location);
      onJobStarted(job_id, file, location);
    } catch (e) {
      setError(e.message || "Upload failed. Is the backend running?");
      setSubmitting(false);
    }
  }

  const locked = !location || submitting;

  return (
    <div className="upload-page">
      <div className="hero">
        <h1>Turn CCTV footage into an explainable accident alert</h1>
        <p className="subtitle">
          Upload traffic or CCTV footage and CrashGuard AI runs full vehicle
          detection, tracking, and anomaly scoring - then shows you exactly
          why it flagged what it flagged, and who to alert nearby.
        </p>
      </div>

      <LocationPicker value={location} onChange={(loc) => { setLocation(loc); setError(null); }} services={services} />

      <p className="upload-step-label">Step 2 &middot; Upload the footage</p>
      <div
        className={`dropzone ${dragOver ? "dropzone-active" : ""} ${!location ? "dropzone-disabled" : ""}`}
        onDragOver={(e) => { e.preventDefault(); if (!locked) setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFile(e.dataTransfer.files?.[0]);
        }}
        onClick={() => {
          if (!location) { setError("Set the camera location on the map first (Step 1)."); return; }
          if (!submitting) inputRef.current?.click();
        }}
      >
        <div className="dropzone-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="30" height="30" fill="none">
            <path d="M12 16V4m0 0L7 9m5-5l5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M4 16v2.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        {submitting ? (
          <p className="dropzone-title">Uploading&hellip;</p>
        ) : !location ? (
          <>
            <p className="dropzone-title">Set the camera location first</p>
            <p className="dropzone-hint">Click the map above or type coordinates, then drop your video here</p>
          </>
        ) : (
          <>
            <p className="dropzone-title">Drop a video here or click to browse</p>
            <p className="dropzone-hint">MP4, MOV, AVI up to {MAX_UPLOAD_MB} MB &mdash; analysis takes 30s&ndash;2min depending on length</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="video/*"
          hidden
          onChange={(e) => { handleFile(e.target.files?.[0]); e.target.value = ""; }}
        />
      </div>

      {error && <p className="error-text">{error}</p>}

      <div className="how-it-works">
        <h3>How it works</h3>
        <div className="how-it-works-grid">
          {STEPS.map((s, i) => (
            <div className="how-step" key={s.title}>
              <div className="how-step-num">{i + 1}</div>
              <div className="how-step-title">{s.title}</div>
              <p className="how-step-body">{s.body}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
