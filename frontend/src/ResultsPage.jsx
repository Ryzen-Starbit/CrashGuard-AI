import { useEffect, useRef, useState } from "react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, ReferenceLine, CartesianGrid,
} from "recharts";
import { getStatus, videoUrl } from "./api";
import EmergencyPanel from "./EmergencyPanel";

const POLL_MS = 2500;

const STAGE_ORDER = ["probing", "detecting", "features", "anomaly", "scoring"];
const STAGE_SHORT = {
  probing: "Read",
  detecting: "Detect",
  features: "Features",
  anomaly: "Anomaly",
  scoring: "Score",
};

const RING_RADIUS = 54;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

export default function ResultsPage({ jobId, fileName, onReset }) {
  const [job, setJob] = useState({ status: "queued" });
  const videoRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    let timer;

    async function poll() {
      try {
        const data = await getStatus(jobId);
        if (cancelled) return;
        setJob(data);
        if (data.status === "queued" || data.status === "processing") {
          timer = setTimeout(poll, POLL_MS);
        }
      } catch (e) {
        if (!cancelled) setJob({ status: "error", error: e.message });
      }
    }
    poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [jobId]);

  const result = job.result;
  const seekTo = (t) => {
    if (videoRef.current) {
      videoRef.current.currentTime = t;
      videoRef.current.play();
    }
  };

  const isBusy = job.status === "queued" || job.status === "processing";
  const pct = job.status === "queued" ? 3 : (job.progress_pct ?? 3);
  const currentStageIdx = STAGE_ORDER.indexOf(job.stage);
  const ringOffset = RING_CIRCUMFERENCE * (1 - pct / 100);

  return (
    <div className="results-page">
      <button className="back-btn" onClick={onReset}>&larr; Analyze another video</button>
      <h2>{fileName}</h2>

      {isBusy && (
        <div className="panel processing-card">
          <div className="progress-ring-wrap">
            <svg viewBox="0 0 120 120" className="progress-ring">
              <circle cx="60" cy="60" r={RING_RADIUS} className="progress-ring-track" />
              <circle
                cx="60" cy="60" r={RING_RADIUS}
                className="progress-ring-fill"
                strokeDasharray={RING_CIRCUMFERENCE}
                strokeDashoffset={ringOffset}
              />
            </svg>
            <div className="progress-ring-label">
              <span className="progress-pct-num">{Math.round(pct)}%</span>
              <span className="progress-pct-caption">
                {job.status === "queued" ? "queued" : "analyzing"}
              </span>
            </div>
          </div>

          <p className="processing-stage">
            {job.status === "queued" ? "Waiting for a worker..." : (job.stage_label || "Processing...")}
          </p>

          <div className="stage-stepper">
            {STAGE_ORDER.map((s, i) => (
              <div
                key={s}
                className={
                  "stage-chip" +
                  (i < currentStageIdx ? " done" : i === currentStageIdx ? " active" : "")
                }
              >
                <span className="stage-dot" />
                {STAGE_SHORT[s]}
              </div>
            ))}
          </div>

          <p className="processing-hint">
            {job.status === "processing" && job.estimated_seconds != null && (
              <>
                {Math.round(job.elapsed_seconds ?? 0)}s elapsed of an estimated ~{job.estimated_seconds}s total
                {job.frame_progress && job.stage === "detecting" && (
                  <> &mdash; frame {job.frame_progress.frame} / {job.frame_progress.total_frames}</>
                )}
              </>
            )}
            {job.status === "processing" && job.estimated_seconds == null && "Reading video..."}
            {job.status === "queued" && "Waiting for a worker to pick this up..."}
          </p>
          <p className="processing-hint processing-hint-sub">
            This runs full YOLOv8 inference on CPU &mdash; longer or busier videos take longer.
          </p>
        </div>
      )}

      {job.status === "error" && (
        <div className="panel verdict-card verdict-error">
          <p>Something went wrong: {job.error}</p>
        </div>
      )}

      {job.status === "done" && result && (
        <div className="results-shell">
          <div className="results-col">
            <div className={`panel verdict-card ${result.accident_detected ? "verdict-alert" : "verdict-clear"}`}>
              <div className="verdict-headline">
                {result.accident_detected ? "⚠ " : ""}{result.headline}
              </div>
              <div className="verdict-meta">
                <span>Confidence: <strong>{(result.confidence * 100).toFixed(0)}%</strong></span>
                <span>Event time: <strong>~{result.event_time_s}s</strong></span>
                <span>Window: <strong>{result.event_window_s[0]}s&ndash;{result.event_window_s[1]}s</strong></span>
              </div>
              <ul className="reasons-list">
                {result.explanation.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
              {result.accident_detected ? (
                <p className="soft-note">
                  This is a prototype; verify manually before acting on this alert.
                </p>
              ) : (
                <p className="soft-note">
                  Still flagged as the clip's most unusual moment &mdash; check it manually if you suspect something happened.
                </p>
              )}
            </div>

            <div className="panel video-panel">
              <video
                ref={videoRef}
                src={videoUrl(jobId)}
                controls
                className="result-video"
              />
            </div>
          </div>

          <div className="results-col">
            <div className="panel chart-panel">
              <h3>Confidence timeline</h3>
              <p className="chart-hint">Click a point on the chart to jump the video there.</p>
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart
                  data={result.timeline}
                  onClick={(e) => {
                    const t = e?.activePayload?.[0]?.payload?.window_start;
                    if (t !== undefined) seekTo(t);
                  }}
                >
                  <defs>
                    <linearGradient id="pGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#e5484d" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#e5484d" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2e" />
                  <XAxis dataKey="window_start" tickFormatter={(v) => `${v}s`} stroke="#888" />
                  <YAxis domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} stroke="#888" />
                  <Tooltip
                    formatter={(v) => [`${(v * 100).toFixed(0)}%`, "P(accident)"]}
                    labelFormatter={(v) => `t = ${v}s`}
                  />
                  <ReferenceLine x={result.event_time_s} stroke="#e5484d" strokeDasharray="4 4" />
                  <Area type="monotone" dataKey="P_accident" stroke="#e5484d" fill="url(#pGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className="panel table-panel">
              <h3>Top candidate moments</h3>
              <table className="candidates-table">
                <thead>
                  <tr><th>Time</th><th>Confidence</th><th></th></tr>
                </thead>
                <tbody>
                  {result.top_candidate_windows.map((r, i) => (
                    <tr key={i}>
                      <td>{r.window_start}s</td>
                      <td>{(r.P_accident * 100).toFixed(0)}%</td>
                      <td><button className="jump-btn" onClick={() => seekTo(r.window_start)}>Jump</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {job.status === "done" && result && job.emergency && (
        <EmergencyPanel
          jobId={jobId}
          emergency={job.emergency}
          result={result}
          initialAlert={job.alert}
        />
      )}
    </div>
  );
}