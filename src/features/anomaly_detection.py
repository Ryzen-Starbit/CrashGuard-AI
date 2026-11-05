import pandas as pd
import numpy as np
from pathlib import Path

BOX_GROWTH_RATE_THRESH = 0.15
NEW_TRACK_SIZE_MULTIPLIER = 1.4
ABRUPT_END_MARGIN = 50
WINDOW_FRAMES = 10  

def compute_box_deformation(df: pd.DataFrame, frame_width=1920, frame_height=1080) -> pd.DataFrame:
    out = []
    for tid, g in df.groupby("track_id"):
        g = g.sort_values("frame").reset_index(drop=True)
        w = g["x2"] - g["x1"]
        h = g["y2"] - g["y1"]
        g["w"], g["h"] = w, h
        g["w_growth"] = w.pct_change(periods=WINDOW_FRAMES).fillna(0)
        g["h_growth"] = h.pct_change(periods=WINDOW_FRAMES).fillna(0)
        g["conf_drop"] = -g["conf"].diff().clip(upper=0).fillna(0)
        g["deforming"] = (
            (g["w_growth"].abs() > BOX_GROWTH_RATE_THRESH) |
            (g["h_growth"].abs() > BOX_GROWTH_RATE_THRESH)
        )
        out.append(g)
    if not out:
        return pd.DataFrame(columns=list(df.columns) + ["w", "h", "w_growth", "h_growth", "conf_drop", "deforming"])
    return pd.concat(out, ignore_index=True)

def find_abrupt_track_ends(df: pd.DataFrame, frame_width=1920, frame_height=1080) -> pd.DataFrame:
    events = []
    max_frame = df["frame"].max() if not df.empty else 0
    for tid, g in df.groupby("track_id"):
        g = g.sort_values("frame")
        last = g.iloc[-1]
        if last["frame"] >= max_frame:
            continue 
        near_edge = (
            last["x1"] < ABRUPT_END_MARGIN or last["x2"] > frame_width - ABRUPT_END_MARGIN or
            last["y1"] < ABRUPT_END_MARGIN or last["y2"] > frame_height - ABRUPT_END_MARGIN
        )
        if not near_edge:
            events.append({
                "track_id": tid,
                "end_frame": last["frame"],
                "end_time": last["timestamp_s"],
                "end_conf": last["conf"],
                "reason": "abrupt_mid_frame_disappearance",
            })
    return pd.DataFrame(events)

def find_anomalous_new_tracks(df: pd.DataFrame) -> pd.DataFrame:
    events = []
    min_frame = df["frame"].min() if not df.empty else 0
    for tid, g in df.groupby("track_id"):
        g = g.sort_values("frame")
        first = g.iloc[0]
        if first["frame"] <= min_frame:
            continue  
        w, h = first["x2"] - first["x1"], first["y2"] - first["y1"]
        frame_at_birth = df[df["frame"] == first["frame"]]
        other_boxes = frame_at_birth[frame_at_birth["track_id"] != tid]
        if other_boxes.empty:
            continue
        median_w = (other_boxes["x2"] - other_boxes["x1"]).median()
        if median_w > 0 and w > median_w * NEW_TRACK_SIZE_MULTIPLIER:
            events.append({
                "track_id": tid,
                "birth_frame": first["frame"],
                "birth_time": first["timestamp_s"],
                "box_width": round(w, 1),
                "typical_width_then": round(median_w, 1),
                "size_ratio": round(w / median_w, 2),
                "reason": "oversized_new_track_likely_merged_boxes",
            })
    return pd.DataFrame(events)

def run_anomaly_pipeline(tracks_csv: str, output_prefix: str, frame_width=1920, frame_height=1080):
    df = pd.read_csv(tracks_csv)
    df = df[df["conf"] >= 0.15]
    Path(output_prefix).parent.mkdir(parents=True, exist_ok=True)
    deform_df = compute_box_deformation(df, frame_width, frame_height)
    abrupt_ends = find_abrupt_track_ends(df, frame_width, frame_height)
    anomalous_births = find_anomalous_new_tracks(df)
    deform_df.to_csv(f"{output_prefix}_deformation.csv", index=False)
    abrupt_ends.to_csv(f"{output_prefix}_abrupt_ends.csv", index=False)
    anomalous_births.to_csv(f"{output_prefix}_anomalous_births.csv", index=False)
    print(f"Abrupt track endings: {len(abrupt_ends)} | Oversized new tracks: {len(anomalous_births)} | "
          f"Deformation-flagged rows: {int(deform_df['deforming'].sum()) if not deform_df.empty else 0}")
    return {
        "deformation": f"{output_prefix}_deformation.csv",
        "abrupt_ends": f"{output_prefix}_abrupt_ends.csv",
        "anomalous_births": f"{output_prefix}_anomalous_births.csv",
    }

if __name__ == "__main__":
    import sys
    tracks = sys.argv[1] if len(sys.argv) > 1 else "data/processed/sample_clip_tracks.csv"
    prefix = sys.argv[2] if len(sys.argv) > 2 else "data/processed/sample_clip_anomaly"
    run_anomaly_pipeline(tracks, prefix)
