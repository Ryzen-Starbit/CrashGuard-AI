# 🚦 CrashGuard AI - Turning CCTV Footage into Accident Alerts

Cities already have thousands of traffic cameras, but almost all of them are passive: the footage is only looked at after someone reports an accident. In the minutes that matter most, nobody is watching. We wanted to flip that around: give the system a CCTV clip and a camera location and get back whether an accident happened, the exact moment it happened, *why* the model thinks so and the nearest hospital and police station to alert.

CrashGuard AI detects and tracks every vehicle in the video, measures the motion signatures of a collision, scores every half-second of footage with a trained classifier and puts it all behind one upload page with a review-and-alert workflow.

![CrashGuard AI results](Screenshots/result.png)

---

## 🎥 Demo

[![CrashGuard AI Demo](https://img.youtube.com/vi/YOUR_VIDEO_ID/maxresdefault.jpg)](https://youtu.be/YOUR_VIDEO_ID)

▶️ **[Watch the full demo on YouTube](https://youtu.be/YOUR_VIDEO_ID)**

---

## The problem we were trying to solve

- **CCTV is recorded, not watched.** Control rooms can't monitor every camera, so accidents are noticed late, through phone calls rather than the cameras already pointed at the road.
- **Black-box detections aren't trusted.** A bare "accident: 87%" doesn't tell an operator what to look at or whether to act.
- **Detection and response are separate steps.** Even once an accident is spotted, someone still has to work out which hospital and police station are closest and contact them.
- **Every second of video needs checking.** Scrubbing through a clip by hand to find the moment of impact is slow.

CrashGuard puts all of this into one flow: upload a clip, set the camera location and get a verdict with the event time, the signals that triggered it, a clickable confidence timeline and the nearest emergency services, with a one-click (simulated) alert after human review.

---

## What it does

### Upload and camera location
The upload page asks for two things: where the camera is and the footage. The location is picked on a Leaflet map of Pune, typed in as coordinates, or chosen from preset landmarks. The demo hospitals and police stations are shown on the same map. Uploads are limited to video files up to 100 MB and unreadable or fake files are rejected before any processing starts.

![Camera location picker](Screenshots/location.png)
![Upload page](Screenshots/upload.png)

### Live processing view
Once a job starts, the backend reports which stage it's on - reading the video, detecting and tracking vehicles, extracting motion features, checking for anomalies and scoring - and the UI shows it as a progress ring with a stage stepper, a frame counter (*"frame 215 / 484"*) and a running time estimate. Jobs are processed one at a time so two uploads don't slow each other down.

![Processing](Screenshots/processing.png)

### Vehicle detection and tracking
Every frame goes through **YOLOv8n**, keeping only cars, motorcycles, buses and trucks. **ByteTrack** links detections across frames, so each vehicle keeps the same ID for as long as it's visible. The result is a track log with every vehicle's box, centre and confidence, frame by frame, timed using the video's real frame rate.

### Collision signals
From the tracks, CrashGuard measures what a crash looks like in motion:

- **Overlap**: bounding boxes of two vehicles intersecting (IoU)
- **Sudden braking**: sharp deceleration right after an overlap
- **Stopping after impact**: a vehicle staying still for more than a second afterwards
- **Box deformation**: a vehicle's box changing shape abruptly
- **Abrupt track endings**: a vehicle disappearing in the middle of the frame instead of driving out of it
- **Merged boxes**: a new track appearing much larger than its neighbours, which usually means two vehicles fused into one box

All of these are grouped into 0.5-second windows and normalised by how many vehicles are on screen, so a busy junction isn't automatically scored as more dangerous than an empty road.

### Accident verdict
A Random Forest classifier gives every window a probability of being an accident. A clip is only flagged when its peak probability is at least **65%** *and* stands at least **0.30** above the clip's own median, which stops noisy clips from triggering alerts everywhere. The verdict card shows the confidence, the estimated event time, the event window and a plain-English list of the signals that fired at that moment, e.g. *"2 vehicles showed abrupt bounding-box deformation"*.

![Accident verdict](Screenshots/verdict.png)

### Confidence timeline
Every window's probability is drawn as a timeline next to the video, with the event time marked. Clicking any point on the chart jumps the video to that moment and a **Top candidate moments** table lists the five highest-scoring windows with a **Jump** button each, so the operator can check the impact in seconds.

![Confidence timeline](Screenshots/timeline.png)

### Emergency response
From the camera location, CrashGuard finds the nearest hospitals and police stations using Haversine distance and estimates an ETA at average city speed. They're drawn on a map with lines to the accident site and the closest hospital and police station are marked as the ones to be alerted. The national emergency numbers (108, 100, 112) are shown alongside.

![Emergency response](Screenshots/emergency.png)

### Sending an alert
After reviewing the video, the operator clicks **Dispatch alert**, optionally with a note for responders. CrashGuard builds a message with the location, a Google Maps link, the confidence, the event time and the detected signals and "sends" it to the nearest hospital and police station. If the model didn't flag an accident, the operator can still send one with a manual override. Every alert is written to an audit log and duplicate alerts for the same job are blocked.

![Alert dispatched](Screenshots/alert.png)

### Normal traffic
When nothing stands out, the result says **No Strong Accident Signal**, but still points to the clip's most unusual moment so the operator can check it manually.

![No accident detected](Screenshots/no-accident.png)

---

## 🏗️ Architecture

```text
┌──────────────────────────────────────────┐
│        Browser (React + Vite)            │
│  Upload · Location picker · Results      │
│  Recharts timeline · Leaflet maps        │
└────────────────────┬─────────────────────┘
                     │ REST (fetch, polling)
                     ▼
┌──────────────────────────────────────────┐
│ FastAPI backend                          │
├──────────────────────────────────────────┤
│ /api/analyze       upload + start a job  │
│ /api/status/{id}   progress + verdict    │
│ /api/video/{id}    stream the clip       │
│ /api/nearby        nearest services      │
│ /api/alert/{id}    dispatch an alert     │
│ /api/alerts        alert audit log       │
└────────────────────┬─────────────────────┘
                     │ background worker
                     ▼
┌──────────────────────────────────────────┐
│ Analysis pipeline (5 stages)             │
│ read video → YOLOv8n + ByteTrack →       │
│ motion features → anomaly features →     │
│ 0.5 s windows → Random Forest →          │
│ verdict, explanation, timeline           │
└────────────────────┬─────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────┐
│ Alerts                                   │
│ nearest hospital / police (Haversine)    │
│ simulated SMS → JSONL audit log          │
└──────────────────────────────────────────┘
```

---

## Tech stack

**Detection and ML**
- Ultralytics YOLOv8n (vehicle detection)
- ByteTrack (multi-object tracking)
- OpenCV (video reading)
- pandas, NumPy, scikit-learn (feature engineering + Random Forest), joblib

**Backend**
- Python, FastAPI, Uvicorn

**Frontend**
- React 19, Vite
- Recharts (confidence timeline)
- Leaflet + OpenStreetMap (location picker and emergency map)

---

## Getting it running

### 1. Clone it

```bash
git clone https://github.com/Ryzen-Starbit/CrashGuardAI.git
cd CrashGuardAI
```

### 2. Backend

```bash
python -m venv venv
```

Activate it:

```bash
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate
```

Install and start:

```bash
pip install -r requirements.txt -r backend/requirements.txt
uvicorn backend.main:app --port 8000
```

Check it at `http://localhost:8000/api/health`. Interactive API docs are at `http://localhost:8000/docs`. On the first analysis, Ultralytics downloads the YOLOv8n weights (about 6 MB), so you need an internet connection the first time.

### 3. Frontend

In a new terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

On Windows, use `copy .env.example .env`. The `.env` file points the app at the backend:

```bash
VITE_API_BASE=http://localhost:8000
```

Open `http://localhost:5173`.

### 4. Command line only

The full pipeline also runs without the web app:

```bash
python predict.py path/to/video.mp4
```

It prints the verdict and saves the per-window scores to `data/processed/`.

### 5. Retraining the classifier

The extracted features for the 20 labelled training clips are included, so the model can be retrained without the original videos:

```bash
python src/classifier/train_classifier.py
```

---

## How to use it

1. Start the backend and frontend and open `http://localhost:5173`.
2. Set the camera location: click a preset chip, click the map, or type coordinates inside Pune.
3. Drop a traffic video onto the upload box.
4. Watch the progress ring move through the stages.
5. Read the verdict: confidence, event time and the signals that fired.
6. Click the peak on the confidence timeline to jump the video to the moment of impact.
7. Scroll to **Emergency response**, check the nearest hospital and police station, add a note and click **Dispatch alert**.
8. Click **Analyze another video** and try a normal-traffic clip to see a "No Strong Accident Signal" result.

---

## 🔗 Project Structure

```text
CrashGuardAI/
├── backend/
│   ├── main.py                 # FastAPI routes, job queue, progress, upload checks
│   └── requirements.txt
│
├── src/
│   ├── detection/
│   │   └── detect_track.py     # YOLOv8n + ByteTrack track log
│   ├── features/
│   │   ├── extract_features.py # speed, braking, overlap, stopping
│   │   ├── anomaly_detection.py# deformation, abrupt ends, merged boxes
│   │   └── unify_features.py   # 0.5 s feature windows
│   ├── classifier/
│   │   ├── train_classifier.py # training + evaluation
│   │   └── model.pkl           # trained Random Forest
│   └── alerts/
│       ├── alert_engine.py     # verdict, explanation, confidence
│       ├── nearby.py           # nearest services + ETA
│       └── dispatch.py         # simulated alerts + audit log
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── UploadPage.jsx      # location + upload
│   │   ├── LocationPicker.jsx  # Leaflet location picker
│   │   ├── ResultsPage.jsx     # progress, verdict, timeline, video
│   │   ├── EmergencyPanel.jsx  # emergency map + dispatch
│   │   ├── mapUtils.js         # Leaflet helpers
│   │   └── api.js              # all backend calls
│   ├── .env.example
│   ├── vite.config.js
│   └── package.json
│
├── data/
│   ├── labels.csv              # clip labels + approximate crash time
│   ├── pune_services.json      # dummy hospitals and police stations
│   └── processed/              # training features
│
├── Screenshots/
├── predict.py                  # command-line pipeline
├── requirements.txt
├── LICENSE
└── README.md
```

---

## Known limitations / things we'd improve

- **The model doesn't generalise yet.** It was trained on only 20 clips (10 accidents, 10 normal). In a leave-one-clip-out test, where each clip is judged by a model that never saw it, the verdict was right on 6 of 20 clips: it caught 3 of 10 accidents and wrongly flagged 7 of 10 normal clips. The pipeline and app work end to end; what's missing is a much larger labelled dataset.
- **Busy traffic looks like a crash.** When vehicles hide behind each other, their boxes deform and tracks vanish, which are the same signals a real collision produces. Clip-relative normalisation and a temporal model over sequences of windows should separate the two better.
- **Labels are coarse.** Crash times are only marked to the nearest second, so the classifier learns from a ±1 s window rather than the exact moment of impact.
- **Alerts are simulated.** Messages are logged rather than sent. Hooking `dispatch.py` up to an SMS or WhatsApp API is the next step.
- **Emergency data is a Pune-only dummy list.** Place names are real landmarks, but coordinates are approximate and phone numbers are placeholders. Pulling real data from the OpenStreetMap Overpass API would make it work anywhere.
- **Distances are straight-line.** ETAs use Haversine distance at an average city speed, not real road routes.
- **Jobs live in memory**, so they're lost when the backend restarts and only uploaded clips are supported, not live RTSP streams.
- **Processing runs on CPU**, so long or busy videos take a while. A GPU or a lighter frame-sampling strategy would make it close to real time.

---

## Contributing

Contributions and suggestions are welcome.

- Fork the repository
- Create a feature branch
- Commit your changes
- Push to your branch
- Submit a pull request

---

## License

Released under the [MIT License](LICENSE).
