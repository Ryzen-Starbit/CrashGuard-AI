import pandas as pd

PEAK_FLOOR = 0.65
PROMINENCE_MARGIN = 0.30
CLUSTER_WINDOW_SEC = 1.0  

def explain_window(row: pd.Series) -> list:
    reasons = []
    if row.get("max_iou", 0) > 0.3:
        reasons.append(f"vehicle bounding boxes overlapped (IoU={row['max_iou']:.2f})")
    if row.get("any_sudden_braking", 0):
        reasons.append("sudden braking / deceleration detected")
    if row.get("any_stopped_after", 0):
        reasons.append("a vehicle stopped shortly after")
    if row.get("n_oversized_births", 0) > 0:
        reasons.append(f"an oversized track appeared (size ratio {row.get('max_size_ratio', 0):.1f}x) "
                        f"-- possible merged/fused vehicle boxes")
    if row.get("n_abrupt_ends", 0) > 0:
        reasons.append(f"{int(row['n_abrupt_ends'])} track(s) disappeared mid-frame")
    if row.get("n_distinct_deforming_tracks", 0) >= 2:
        reasons.append(f"{int(row['n_distinct_deforming_tracks'])} vehicles showed abrupt bounding-box deformation")
    return reasons or ["no strong individual signal -- flagged on combined score only"]

def build_verdict(scored_windows: pd.DataFrame, clip_id: str = "clip") -> dict:
    df = scored_windows.sort_values("window_start").reset_index(drop=True)
    peak_idx = df["P_accident"].idxmax()
    peak_row = df.loc[peak_idx]
    peak_p = float(peak_row["P_accident"])
    peak_t = float(peak_row["window_start"])
    median_p = float(df["P_accident"].median())
    prominence = peak_p - median_p
    is_accident = (peak_p >= PEAK_FLOOR) and (prominence >= PROMINENCE_MARGIN)
    cluster = df[(df["window_start"] >= peak_t - CLUSTER_WINDOW_SEC) &
                 (df["window_start"] <= peak_t + CLUSTER_WINDOW_SEC)]
    top5 = df.sort_values("P_accident", ascending=False).head(5)
    verdict = {
        "clip_id": clip_id,
        "accident_detected": bool(is_accident),
        "headline": "Possible Accident -- Review Recommended" if is_accident else "No Strong Accident Signal",
        "confidence": round(peak_p, 3),
        "prominence": round(prominence, 3),
        "event_time_s": peak_t,
        "event_window_s": [round(cluster["window_start"].min(), 1), round(cluster["window_start"].max() + 0.5, 1)],
        "explanation": explain_window(peak_row),
        "top_candidate_windows": top5[["window_start", "P_accident"]].to_dict("records"),
    }
    return verdict

def format_verdict(v: dict) -> str:
    lines = []
    if v["accident_detected"]:
        lines.append(f"{v['headline']} -- {v['clip_id']}")
        lines.append(f"  Time: ~{v['event_time_s']}s (event window {v['event_window_s'][0]}s-{v['event_window_s'][1]}s)")
        lines.append(f"  Confidence: {v['confidence']:.0%}  (prominence over clip baseline: {v['prominence']:.2f})")
        lines.append("  Signals seen at this moment:")
        for r in v["explanation"]:
            lines.append(f"    - {r}")
        lines.append("  This is a prototype; verify manually.")
    else:
        lines.append(f"{v['headline']} in {v['clip_id']}")
        lines.append(f"  Highest-scoring moment: ~{v['event_time_s']}s "
                      f"(P={v['confidence']:.0%}, below the {PEAK_FLOOR:.0%} confidence "
                      f"or {PROMINENCE_MARGIN:.2f} prominence bar)")
        lines.append("  If you believe there IS an accident here, check this timestamp manually --")
        lines.append("  it's still the clip's most anomalous moment, just not confident enough to auto-alert.")
    lines.append("\n  Top candidate moments (ranked):")
    for r in v["top_candidate_windows"]:
        lines.append(f"    t={r['window_start']:5.1f}s  P(accident)={r['P_accident']:.2f}")
    return "\n".join(lines)