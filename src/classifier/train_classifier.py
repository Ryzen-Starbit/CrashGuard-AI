import sys
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit, LeaveOneGroupOut
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score

CLIP_ALERT_THRESHOLD = 0.5  

LABEL_TOLERANCE_SEC = 1.0

FEATURE_COLS = [
    "max_iou",
    "any_sudden_braking",
    "any_stopped_after",
    "n_abrupt_ends",
    "n_oversized_births",
    "max_size_ratio",
    "n_deforming_track_frames",
    "n_distinct_deforming_tracks",
    "abrupt_end_rate",
    "oversized_birth_rate",
    "deforming_track_rate",
]

def load_labels(labels_csv: str) -> pd.DataFrame:
    df = pd.read_csv(labels_csv)
    df["crash_time_approx"] = pd.to_numeric(df["crash_time_approx"], errors="coerce")
    return df

def build_training_table(processed_dir: str, labels_csv: str) -> pd.DataFrame:
    labels = load_labels(labels_csv)
    processed_path = Path(processed_dir)
    all_rows = []
    for _, row in labels.iterrows():
        clip_id = row["clip_id"]
        clip_label = int(row["label"])
        crash_time = row["crash_time_approx"]
        feat_path = processed_path / f"{clip_id}_unified_features.csv"
        if not feat_path.exists():
            print(f"  [skip] no unified_features for {clip_id}")
            continue
        feats = pd.read_csv(feat_path)
        if feats.empty:
            print(f"  [skip] empty unified_features for {clip_id}")
            continue
        for c in FEATURE_COLS:
            if c not in feats.columns:
                feats[c] = 0
            elif feats[c].dtype == bool:
                feats[c] = feats[c].astype(int)
            elif feats[c].dtype == object:
                mapped = feats[c].astype(str).str.lower().map({"true": 1, "false": 0})
                feats[c] = mapped.where(mapped.notna(), pd.to_numeric(feats[c], errors="coerce")).fillna(0)
        feats["clip_id"] = clip_id
        if clip_label == 1 and pd.notna(crash_time):
            feats["window_label"] = (
                (feats["window_start"] >= crash_time - LABEL_TOLERANCE_SEC) &
                (feats["window_start"] <= crash_time + LABEL_TOLERANCE_SEC)
            ).astype(int)
        else:
            feats["window_label"] = 0
        all_rows.append(feats)
    table = pd.concat(all_rows, ignore_index=True)
    for c in FEATURE_COLS:
        table[c] = pd.to_numeric(table[c], errors="coerce").fillna(0)
    return table

def train(processed_dir: str, labels_csv: str, model_out: str):
    print("Building training table from all clips...")
    table = build_training_table(processed_dir, labels_csv)
    n_pos = table["window_label"].sum()
    n_total = len(table)
    print(f"\n{n_total} total windows across {table['clip_id'].nunique()} clips "
          f"({n_pos} positive / accident windows, {n_total - n_pos} negative)")
    X = table[FEATURE_COLS]
    y = table["window_label"]
    groups = table["clip_id"]
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=42)
    train_idx, test_idx = next(splitter.split(X, y, groups))
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=6,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
    )
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]
    print("\n=== Held-out clip evaluation (window-level) ===")
    print(classification_report(y_test, y_pred, target_names=["normal", "accident"], zero_division=0))
    print("Confusion matrix [[TN FP][FN TP]]:")
    print(confusion_matrix(y_test, y_pred))
    if len(set(y_test)) > 1:
        print(f"ROC-AUC: {roc_auc_score(y_test, y_proba):.3f}")
    print("\nFeature importances:")
    for name, imp in sorted(zip(FEATURE_COLS, clf.feature_importances_), key=lambda x: -x[1]):
        print(f"  {name:30s} {imp:.3f}")
    print("\n=== Clip-level evaluation (leave-one-clip-out) ===")
    clip_labels = table.groupby("clip_id")["window_label"].max()  
    logo = LeaveOneGroupOut()
    clip_correct, clip_results = 0, []
    for train_i, test_i in logo.split(X, y, groups):
        test_clip = groups.iloc[test_i].iloc[0]
        true_label = clip_labels[test_clip]
        m = RandomForestClassifier(
            n_estimators=300, max_depth=6, min_samples_leaf=2,
            class_weight="balanced", random_state=42,
        )
        m.fit(X.iloc[train_i], y.iloc[train_i])
        proba = m.predict_proba(X.iloc[test_i])[:, 1]
        pred_label = int((proba >= CLIP_ALERT_THRESHOLD).any())
        clip_correct += int(pred_label == true_label)
        clip_results.append((test_clip, true_label, pred_label, round(proba.max(), 3)))
    for clip_id, true_l, pred_l, max_p in sorted(clip_results):
        mark = "OK " if true_l == pred_l else "MISS"
        print(f"  [{mark}] {clip_id:14s} true={true_l} pred={pred_l} max_P(accident)={max_p}")
    print(f"\nClip-level accuracy (leave-one-out): {clip_correct}/{len(clip_results)} "
          f"= {clip_correct/len(clip_results):.0%}")
    clf_final = RandomForestClassifier(
        n_estimators=300,
        max_depth=6,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
    )
    clf_final.fit(X, y)
    Path(model_out).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": clf_final, "feature_cols": FEATURE_COLS}, model_out)
    print(f"\nFinal model (trained on all {n_total} windows) saved to {model_out}")
    return clf_final

if __name__ == "__main__":
    processed_dir = sys.argv[1] if len(sys.argv) > 1 else "data/processed"
    labels_csv = sys.argv[2] if len(sys.argv) > 2 else "data/labels.csv"
    model_out = sys.argv[3] if len(sys.argv) > 3 else "src/classifier/model.pkl"
    train(processed_dir, labels_csv, model_out)
