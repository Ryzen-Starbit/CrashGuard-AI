import pandas as pd
from pathlib import Path

WINDOW_SEC = 0.5

def _safe_read(path):
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
        return df
    except pd.errors.EmptyDataError:
        return pd.DataFrame()

def build_unified_features(events_v2_csv, abrupt_ends_csv, anomalous_births_csv, deform_csv,
                            clip_duration_s: float = None, tracks_csv: str = None):
    events = _safe_read(events_v2_csv)
    abrupt = _safe_read(abrupt_ends_csv)
    births = _safe_read(anomalous_births_csv)
    deform = _safe_read(deform_csv)
    tracks = _safe_read(tracks_csv) if tracks_csv else pd.DataFrame()

    def bucket(t):
        return round(t / WINDOW_SEC) * WINDOW_SEC

    if not events.empty:
        events["bucket"] = events["event_time"].apply(bucket)
    if not abrupt.empty:
        abrupt["bucket"] = abrupt["end_time"].apply(bucket)
    if not births.empty:
        births["bucket"] = births["birth_time"].apply(bucket)
    deform_true = deform[deform["deforming"]].copy() if (not deform.empty and "deforming" in deform.columns) else pd.DataFrame()
    if not deform_true.empty:
        deform_true["bucket"] = deform_true["timestamp_s"].apply(bucket)
    all_buckets = set()
    if not events.empty:
        all_buckets |= set(events["bucket"])
    if not abrupt.empty:
        all_buckets |= set(abrupt["bucket"])
    if not births.empty:
        all_buckets |= set(births["bucket"])
    if not deform_true.empty:
        all_buckets |= set(deform_true["bucket"])
    if clip_duration_s:
        import numpy as np
        all_buckets |= set(bucket(t) for t in np.arange(0, clip_duration_s, WINDOW_SEC))
    if not tracks.empty:
        tracks["bucket"] = tracks["timestamp_s"].apply(bucket)
    rows = []
    for b in sorted(all_buckets):
        ev = events[events["bucket"] == b] if not events.empty else pd.DataFrame()
        ab = abrupt[abrupt["bucket"] == b] if not abrupt.empty else pd.DataFrame()
        bi = births[births["bucket"] == b] if not births.empty else pd.DataFrame()
        de = deform_true[deform_true["bucket"] == b] if not deform_true.empty else pd.DataFrame()
        if not tracks.empty:
            active = tracks[tracks["bucket"] == b]
            n_active = max(active["track_id"].nunique(), 1)
        else:
            n_active = 1  
        n_abrupt_ends = len(ab)
        n_oversized_births = len(bi)
        n_deforming_track_frames = len(de)
        n_distinct_deforming_tracks = de["track_id"].nunique() if not de.empty else 0
        rows.append({
            "window_start": b,
            "n_active_tracks": n_active,
            "max_iou": ev["iou"].max() if not ev.empty else 0.0,
            "any_sudden_braking": bool(ev["sudden_braking"].any()) if not ev.empty else False,
            "any_stopped_after": bool(ev["stopped_after_event"].any()) if not ev.empty else False,
            "n_abrupt_ends": n_abrupt_ends,
            "n_oversized_births": n_oversized_births,
            "max_size_ratio": bi["size_ratio"].max() if not bi.empty else 0.0,
            "n_deforming_track_frames": n_deforming_track_frames,
            "n_distinct_deforming_tracks": n_distinct_deforming_tracks,
            "abrupt_end_rate": n_abrupt_ends / n_active,
            "oversized_birth_rate": n_oversized_births / n_active,
            "deforming_track_rate": n_distinct_deforming_tracks / n_active,
        })
    return pd.DataFrame(rows).sort_values("window_start").reset_index(drop=True)

if __name__ == "__main__":
    import sys
    prefix = sys.argv[1] if len(sys.argv) > 1 else "sample_clip"
    df = build_unified_features(
        events_v2_csv=f"data/processed/{prefix}_events_v2.csv",
        abrupt_ends_csv=f"data/processed/{prefix}_anomaly_abrupt_ends.csv",
        anomalous_births_csv=f"data/processed/{prefix}_anomaly_anomalous_births.csv",
        deform_csv=f"data/processed/{prefix}_anomaly_deformation.csv",
    )
    out = f"data/processed/{prefix}_unified_features.csv"
    df.to_csv(out, index=False)
    print(df.to_string())
