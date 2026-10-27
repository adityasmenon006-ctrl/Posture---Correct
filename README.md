# PostureCorrect

A real-time, computer-vision-powered posture monitor for people who spend long hours at a desk. Using only a standard webcam, PostureCorrect tracks your head and shoulder alignment and alerts you when you have been slouching for too long.

**Privacy first:** all processing happens locally on your machine. No video is saved or sent anywhere.

> PostureCorrect is a posture-*awareness* tool. It is not a medical device and does not diagnose or treat any condition.

---

## Table of Contents

1. [How It Works](#how-it-works)
2. [Features](#features)
3. [Tech Stack](#tech-stack)
4. [Setup Guide](#setup-guide)
5. [Running the App](#running-the-app)
6. [Configuration](#configuration)
7. [Troubleshooting](#troubleshooting)
8. [Glossary](#glossary)
9. [Limitations](#limitations)
10. [Future Scope](#future-scope)

---

## How It Works

```
Webcam -> Pose Landmarks -> Posture Measurement -> Decision -> Alert
```

1. **Capture:** OpenCV reads frames from the webcam.
2. **Detect:** MediaPipe's pose model finds body landmarks (nose and shoulders matter most here).
3. **Measure:** the program computes `head_drop`, the vertical distance between the nose and the average shoulder height.
4. **Compare:** `head_drop` is compared to your personal baseline, recorded during calibration.
5. **Alert:** if your head stays lower than baseline + margin for several seconds, a warning appears and a beep sounds.

The ML part is the pretrained MediaPipe pose model. The posture logic on top of it (calibration, threshold, persistence check) is simple rule-based code.

---

## Features

- Live skeleton overlay on the webcam feed
- Manual calibration: press `C` when you are sitting properly
- Steadiness check that rejects calibrations where you moved too much
- Optional sanity limit that rejects a slouched baseline
- Persistence check, so brief movements do not trigger false alarms
- On-screen status (good, checking, poor posture) plus a beep alert
- Runs entirely offline

---

## Tech Stack

| Tool | Purpose |
|---|---|
| Python 3.10+ | Programming language |
| OpenCV (`opencv-python`) | Webcam capture, drawing, display window |
| MediaPipe (Tasks API) | Pretrained pose-landmark detection |
| NumPy | Numerical support library |
| `winsound` | Alert beep (built into Windows) |

---

## Setup Guide

### Prerequisites

- **Windows 10/11** (the beep uses `winsound`, which is Windows-only; see [Troubleshooting](#troubleshooting) for other systems)
- **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/). During installation, tick **"Add Python to PATH"**.
- A **webcam**
- **Git** (optional, only if you clone the repo)

Check Python is installed:

```
python --version
```

### 1. Get the code

```
git clone https://github.com/adityasmenon006-ctrl/Posture---Correct.git
cd Posture---Correct
```

Or download the ZIP from GitHub and extract it.

### 2. Create a virtual environment

A **virtual environment** (venv) is an isolated folder holding this project's Python libraries, so they do not mix with other projects on your computer.

```
python -m venv venv
```

### 3. Activate the virtual environment

| Shell | Command |
|---|---|
| Windows Command Prompt | `venv\Scripts\activate` |
| Windows PowerShell | `.\venv\Scripts\Activate.ps1` |
| macOS / Linux | `source venv/bin/activate` |

When it works, `(venv)` appears at the start of your terminal line.

**PowerShell says "running scripts is disabled"?** Either switch to Command Prompt, or run this once:

```
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

You must activate the environment **every time** you open a new terminal to work on the project.

### 4. Install dependencies

```
pip install opencv-python mediapipe numpy
```

Or, if the repo includes a `requirements.txt`:

```
pip install -r requirements.txt
```

### 5. Download the pose model

Current MediaPipe needs a separate model file. Download it into the project folder (next to `main.py`):

```
curl -L -o pose_landmarker.task https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task
```

You should now see `pose_landmarker.task` in the folder.

---

## Running the App

With the virtual environment active and your terminal inside the project folder:

```
python main.py
```

### Controls

| Key | Action |
|---|---|
| `C` | Start (or restart) calibration |
| `Q` | Quit |

Click the video window first so it receives the key presses.

### Using it

1. Run the program. It waits for you to calibrate.
2. Sit upright in your normal good posture and press `C`.
3. A 5-second countdown lets you settle, then 3 seconds of readings are taken. Hold still.
4. If you moved too much, it asks you to retry.
5. After calibration, the status line shows **Good posture**, **Checking...** or **POOR POSTURE**.

Recalibrate whenever you move your chair or webcam.

---

## Configuration

Settings live at the top of `main.py`.

| Setting | Default | What it does |
|---|---|---|
| `GET_READY_SECONDS` | 5 | Countdown after pressing `C` |
| `CALIBRATION_SECONDS` | 3 | How long readings are collected |
| `MARGIN` | 0.01 | Drop allowed beyond baseline. Smaller is more sensitive |
| `MAX_SPREAD` | 0.05 | Calibration fails if readings vary more than this |
| `MAX_BASELINE` | `None` | Optional limit that rejects a slouched baseline |
| `PERSISTENCE_SECONDS` | 3 | How long bad posture must last before the alert |
| `cv2.VideoCapture(0)` | 0 | Camera index. Use `1` for an external webcam |

**Tuning `MAX_BASELINE`:** calibrate once sitting upright and once slouching, note the `avg=` value printed in the terminal each time, then set `MAX_BASELINE` between the two values.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` is not recognized | Reinstall Python and tick "Add Python to PATH" |
| `No module named 'cv2'` | The venv is not active, or was created in a folder that has since moved. Delete `venv`, recreate it, and reinstall dependencies |
| `module 'mediapipe' has no attribute 'solutions'` | Newer MediaPipe removed the old `solutions` API. This project already uses the Tasks API, so make sure you are running the latest `main.py` |
| Model file not found | Confirm `pose_landmarker.task` is in the same folder as `main.py` |
| Black window or no video | Close other apps using the webcam. Try camera index `0`, `1` or `2` |
| `WinError 4551: An Application Control policy has blocked this file` | Windows Smart App Control is blocking MediaPipe's native library. Open Windows Security, go to App & browser control, then Smart App Control, and turn it off, then restart. Recent Windows updates allow turning it back on later |
| `winsound` import error on macOS/Linux | `winsound` is Windows-only. Remove the import and the `winsound.Beep(...)` line, or replace it with another sound library |
| Landmarks jump around | Improve lighting and keep your head and shoulders fully in frame |

---

## Glossary

**Computer vision:** the field of getting computers to understand images and video.

**Pose estimation:** detecting the positions of body parts (head, shoulders, elbows, and so on) in an image.

**Landmark:** a single detected body point, given as x and y coordinates. MediaPipe returns 33 per person.

**Normalized coordinates:** positions given as a fraction of the frame (0 to 1) rather than pixels. Multiply by frame width or height to get pixels.

**Pretrained model:** an AI model already trained by someone else. We only run it (inference) and never train it ourselves.

**Inference:** using a trained model to make predictions on new data.

**MediaPipe:** Google's open-source framework for ML tasks such as pose detection.

**OpenCV:** an open-source library for image and video processing.

**Virtual environment (venv):** an isolated folder of Python packages for one project.

**Baseline:** your personal "good posture" reading, taken during calibration.

**Calibration:** recording your baseline so detection is relative to you rather than a generic value.

**Threshold / margin:** the cutoff between acceptable and poor posture. Here, baseline plus `MARGIN`.

**Persistence check:** requiring poor posture to last several seconds before alerting, to avoid false alarms.

**Frame:** a single image from the video stream.

---

## Limitations

- Calibration assumes you sit correctly at that moment. The steadiness check and optional `MAX_BASELINE` reduce, but cannot remove, this risk.
- Accuracy drops in poor lighting, with extreme camera angles, or when your shoulders are out of frame.
- The measurement is a simple 2D estimate and does not capture all aspects of posture.
- The frame rate is assumed to be 30 FPS for timestamps, not measured.
- The baseline is not saved between sessions.
- The beep currently repeats while poor posture continues.

---

## Future Scope

- Save the baseline between sessions
- Smarter alerts based on duration and patterns
- Neck-angle measurement instead of only vertical drop
- Posture history and wellness analytics that store only numbers, never video
- A friendlier interface (for example, a Streamlit app)
- A trained classifier on landmark features to replace the fixed threshold

---

## License

Add your preferred license here (for example MIT).

## Acknowledgements

- [MediaPipe](https://github.com/google-ai-edge/mediapipe) by Google
- [OpenCV](https://opencv.org/)
