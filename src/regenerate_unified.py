import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from features.unify_features import build_unified_features

processed = Path("data/processed")
labels_clip_ids = [p.stem.replace("_tracks", "") for p in processed.glob("*_tracks.csv")]

for clip_id in sorted(labels_clip_ids):
    df = build_unified_features(
        events_v2_csv=processed / f"{clip_id}_events_v2.csv",
        abrupt_ends_csv=processed / f"{clip_id}_anomaly_abrupt_ends.csv",
        anomalous_births_csv=processed / f"{clip_id}_anomaly_anomalous_births.csv",
        deform_csv=processed / f"{clip_id}_anomaly_deformation.csv",
        tracks_csv=processed / f"{clip_id}_tracks.csv",
    )
    out = processed / f"{clip_id}_unified_features.csv"
    df.to_csv(out, index=False)
    print(f"{clip_id}: {len(df)} windows -> {out}")
