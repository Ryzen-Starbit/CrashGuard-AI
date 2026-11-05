import csv
from pathlib import Path
import cv2
from ultralytics import YOLO

VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


def read_video_meta(video_path: str):
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    if not fps or fps <= 1 or fps > 240:
        fps = 30.0
    return fps, total_frames


def run_tracking(video_path: str, output_csv: str, model_name: str = "yolov8n.pt", conf: float = 0.25,
                 on_progress=None, progress_every: int = 5):
    model = YOLO(model_name)
    fps, total_frames = read_video_meta(video_path)
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    n_rows = 0
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "timestamp_s", "track_id", "class", "x1", "y1", "x2", "y2", "cx", "cy", "conf"])
        results = model.track(
            source=str(video_path),
            classes=list(VEHICLE_CLASSES.keys()),
            tracker="bytetrack.yaml",
            persist=True,
            stream=True,
            conf=conf,
            verbose=False,
        )
        for frame_idx, r in enumerate(results):
            if on_progress and frame_idx % progress_every == 0:
                on_progress(frame_idx, total_frames)
            if r.boxes is None or r.boxes.id is None:
                continue
            boxes = r.boxes.xyxy.cpu().numpy()
            ids = r.boxes.id.cpu().numpy().astype(int)
            clss = r.boxes.cls.cpu().numpy().astype(int)
            confs = r.boxes.conf.cpu().numpy()
            timestamp = frame_idx / fps
            for box, tid, cls, conf_val in zip(boxes, ids, clss, confs):
                x1, y1, x2, y2 = box
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                writer.writerow([
                    frame_idx, round(timestamp, 3), tid,
                    VEHICLE_CLASSES.get(cls, "unknown"),
                    round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1),
                    round(cx, 1), round(cy, 1), round(float(conf_val), 3),
                ])
                n_rows += 1
    if on_progress:
        on_progress(total_frames, total_frames)
    print(f"Track log saved to {output_csv} ({n_rows} rows, {fps:.1f} fps)")
    return output_csv


if __name__ == "__main__":
    import sys
    video = sys.argv[1] if len(sys.argv) > 1 else "data/raw_videos/accidents/crash_001.mp4"
    out = sys.argv[2] if len(sys.argv) > 2 else "data/processed/crash_001_tracks.csv"
    run_tracking(video_path=video, output_csv=out)
