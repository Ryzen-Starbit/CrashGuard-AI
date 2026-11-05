import pandas as pd
import numpy as np
from pathlib import Path
from itertools import combinations

MIN_CONFIDENCE = 0.35
MIN_TRACK_LEN = 10
STOP_SPEED_THRESH = 5.0
IOU_OVERLAP_THRESH = 0.05


def compute_iou(box1, box2):
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0

def clean_tracks(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["conf"] >= MIN_CONFIDENCE].copy()
    track_lens = df.groupby("track_id")["frame"].count()
    valid_ids = track_lens[track_lens >= MIN_TRACK_LEN].index
    return df[df["track_id"].isin(valid_ids)].sort_values(["track_id", "frame"])

def compute_per_track_motion(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for tid, g in df.groupby("track_id"):
        g = g.sort_values("frame").reset_index(drop=True)
        dt = g["timestamp_s"].diff().replace(0, np.nan)
        dx = g["cx"].diff()
        dy = g["cy"].diff()
        speed = np.sqrt(dx**2 + dy**2) / dt
        accel = speed.diff() / dt
        g["speed"] = speed.fillna(0)
        g["accel"] = accel.fillna(0)
        g["is_stopped"] = g["speed"] < STOP_SPEED_THRESH
        stop_groups = (g["is_stopped"] != g["is_stopped"].shift()).cumsum()
        g["stop_run_len"] = g.groupby(stop_groups)["is_stopped"].transform("size")
        dt_median = dt.median()
        dt_median = dt_median if pd.notna(dt_median) and dt_median > 0 else (1 / 30)
        g["stopped_duration_s"] = np.where(
            g["is_stopped"], g["stop_run_len"] * dt_median, 0
        )
        out.append(g)
    if not out:
        return pd.DataFrame(columns=list(df.columns) + ["speed", "accel", "is_stopped", "stop_run_len", "stopped_duration_s"])
    return pd.concat(out, ignore_index=True)

def compute_pairwise_overlap(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for frame, g in df.groupby("frame"):
        rows = g.to_dict("records")
        for a, b in combinations(rows, 2):
            box_a = (a["x1"], a["y1"], a["x2"], a["y2"])
            box_b = (b["x1"], b["y1"], b["x2"], b["y2"])
            iou = compute_iou(box_a, box_b)
            if iou > IOU_OVERLAP_THRESH:
                records.append({
                    "frame": frame,
                    "timestamp_s": a["timestamp_s"],
                    "track_id_a": a["track_id"],
                    "track_id_b": b["track_id"],
                    "iou": round(iou, 4),
                })
    return pd.DataFrame(records)

def build_event_windows(motion_df: pd.DataFrame, overlap_df: pd.DataFrame,
                         window_sec: float = 1.0, decel_threshold: float = -150.0) -> pd.DataFrame:
    events = []
    for _, row in overlap_df.iterrows():
        t = row["timestamp_s"]
        for tid_col in ["track_id_a", "track_id_b"]:
            tid = row[tid_col]
            track = motion_df[motion_df["track_id"] == tid]
            window = track[(track["timestamp_s"] >= t) & (track["timestamp_s"] <= t + window_sec)]
            if window.empty:
                continue
            min_accel = window["accel"].min()
            max_stop_dur = window["stopped_duration_s"].max()
            events.append({
                "event_time": t,
                "track_id": tid,
                "partner_track_id": row["track_id_b"] if tid_col == "track_id_a" else row["track_id_a"],
                "iou": row["iou"],
                "min_accel": round(min_accel, 2),
                "sudden_braking": min_accel < decel_threshold,
                "post_event_stop_duration_s": round(max_stop_dur, 2),
                "stopped_after_event": max_stop_dur > 1.0,
            })
    return pd.DataFrame(events)

def run_pipeline(tracks_csv: str, output_csv: str):
    df = pd.read_csv(tracks_csv)
    df = clean_tracks(df)
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    cols = ["event_time", "track_id", "partner_track_id", "iou",
            "min_accel", "sudden_braking", "post_event_stop_duration_s", "stopped_after_event"]
    if df.empty:
        pd.DataFrame(columns=cols).to_csv(output_csv, index=False)
        print("No valid tracks after cleaning.")
        return output_csv
    motion_df = compute_per_track_motion(df)
    overlap_df = compute_pairwise_overlap(df)
    if overlap_df.empty:
        pd.DataFrame(columns=cols).to_csv(output_csv, index=False)
        print("No overlapping tracks found.")
        return output_csv
    events_df = build_event_windows(motion_df, overlap_df)
    events_df.to_csv(output_csv, index=False)
    print(f"{len(events_df)} candidate event-rows saved to {output_csv}")
    return output_csv

if __name__ == "__main__":
    import sys
    tracks = sys.argv[1] if len(sys.argv) > 1 else "data/processed/sample_clip_tracks.csv"
    out = sys.argv[2] if len(sys.argv) > 2 else "data/processed/sample_clip_events_v2.csv"
    run_pipeline(tracks, out)
