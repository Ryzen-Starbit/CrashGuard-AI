import { useState } from "react";
import UploadPage from "./UploadPage";
import ResultsPage from "./ResultsPage";
import "./App.css";

export default function App() {
  const [job, setJob] = useState(null);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
                <path d="M3 13l2-6a2 2 0 0 1 2-1.4h10a2 2 0 0 1 2 1.4l2 6"
                  stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                <rect x="2.3" y="13" width="19.4" height="5.6" rx="1.7" stroke="currentColor" strokeWidth="1.7" />
                <circle cx="7.2" cy="18.8" r="1.5" fill="currentColor" />
                <circle cx="16.8" cy="18.8" r="1.5" fill="currentColor" />
              </svg>
            </span>
            <span className="brand-name">CrashGuard&nbsp;<span className="brand-accent">AI</span></span>
          </div>
          <span className="topbar-badge">Candidate-alert system</span>
        </div>
      </header>

      <main className="app-main">
        {!job ? (
          <UploadPage
            onJobStarted={(jobId, file) => setJob({ jobId, fileName: file.name })}
          />
        ) : (
          <ResultsPage
            jobId={job.jobId}
            fileName={job.fileName}
            onReset={() => setJob(null)}
          />
        )}
      </main>
    </div>
  );
}