import sys
import argparse
from pathlib import Path
import cv2
import joblib

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.detection.detect_track import run_tracking, read_video_meta
from src.features.extract_features import run_pipeline as run_events_pipeline
from src.features.anomaly_detection import run_anomaly_pipeline
from src.features.unify_features import build_unified_features
from src.alerts.alert_engine import build_verdict, format_verdict

MODEL_PATH = Path(__file__).parent / "src" / "classifier" / "model.pkl"

DETECT_START, DETECT_END = 5, 75
FEATURES_PCT, ANOMALY_PCT, SCORING_PCT = 75, 85, 93


def get_video_info(video_path: str):
    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    fps, n_frames = read_video_meta(video_path)
    return width, height, n_frames / fps


def predict(video_path: str, processed_dir: str = "data/processed", model_path: Path = MODEL_PATH,
            keep_intermediate: bool = True, progress=None):
    def report(stage, pct, frame=None, total=None):
        if progress:
            progress(stage, pct, frame, total)

    video_path = str(video_path)
    clip_id = Path(video_path).stem
    processed = Path(processed_dir)
    processed.mkdir(parents=True, exist_ok=True)

    report("probing", 2)
    width, height, duration = get_video_info(video_path)
    print(f"=== CrashGuard AI: analyzing {clip_id} ({width}x{height}, {duration:.1f}s) ===\n")

    tracks_csv = processed / f"{clip_id}_tracks.csv"
    events_csv = processed / f"{clip_id}_events_v2.csv"
    anomaly_prefix = str(processed / f"{clip_id}_anomaly")
    unified_csv = processed / f"{clip_id}_unified_features.csv"
    scored_csv = processed / f"{clip_id}_scored.csv"
    intermediates = [
        tracks_csv, events_csv, unified_csv,
        Path(f"{anomaly_prefix}_deformation.csv"),
        Path(f"{anomaly_prefix}_abrupt_ends.csv"),
        Path(f"{anomaly_prefix}_anomalous_births.csv"),
    ]

    def on_frame(frame, total):
        frac = min(frame / total, 1.0) if total else 0.0
        report("detecting", DETECT_START + frac * (DETECT_END - DETECT_START), frame, total)

    try:
        print("[1/4] Detecting + tracking vehicles (YOLOv8n + ByteTrack)...")
        report("detecting", DETECT_START)
        run_tracking(video_path=video_path, output_csv=str(tracks_csv), on_progress=on_frame)

        print("\n[2/4] Extracting overlap / braking / stop features...")
        report("features", FEATURES_PCT)
        run_events_pipeline(tracks_csv=str(tracks_csv), output_csv=str(events_csv))

        print("\n[3/4] Extracting anomaly signals (deformation, abrupt ends, oversized births)...")
        report("anomaly", ANOMALY_PCT)
        run_anomaly_pipeline(tracks_csv=str(tracks_csv), output_prefix=anomaly_prefix,
                             frame_width=width, frame_height=height)

        print("\n[4/4] Unifying features and scoring with the trained classifier...")
        report("scoring", SCORING_PCT)
        unified = build_unified_features(
            events_v2_csv=str(events_csv),
            abrupt_ends_csv=f"{anomaly_prefix}_abrupt_ends.csv",
            anomalous_births_csv=f"{anomaly_prefix}_anomalous_births.csv",
            deform_csv=f"{anomaly_prefix}_deformation.csv",
            clip_duration_s=duration,
            tracks_csv=str(tracks_csv),
        )
        unified.to_csv(unified_csv, index=False)
        if unified.empty:
            print("\nNo vehicle activity detected in this clip -- nothing to score.")
            return None

        bundle = joblib.load(model_path)
        model, feature_cols = bundle["model"], bundle["feature_cols"]
        scored = unified.copy()
        for c in ["any_sudden_braking", "any_stopped_after"]:
            if scored[c].dtype == bool:
                scored[c] = scored[c].astype(int)
        for c in feature_cols:
            if c not in scored.columns:
                scored[c] = 0
        scored["P_accident"] = model.predict_proba(scored[feature_cols])[:, 1]
        scored.to_csv(scored_csv, index=False)

        verdict = build_verdict(scored, clip_id=clip_id)
        verdict["timeline"] = [
            {"window_start": float(r.window_start), "P_accident": round(float(r.P_accident), 4)}
            for r in scored[["window_start", "P_accident"]].itertuples()
        ]
        report("scoring", 100)
        print("\n" + "=" * 60)
        print(format_verdict(verdict))
        print("=" * 60)
        print(f"\nFull per-window scores saved to {scored_csv}")
        return verdict
    finally:
        if not keep_intermediate:
            for p in intermediates + [scored_csv]:
                Path(p).unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run CrashGuard AI on a video.")
    parser.add_argument("video", help="Path to the input video file")
    parser.add_argument("--processed-dir", default="data/processed")
    parser.add_argument("--model", default=str(MODEL_PATH))
    args = parser.parse_args()
    predict(args.video, processed_dir=args.processed_dir, model_path=Path(args.model))
