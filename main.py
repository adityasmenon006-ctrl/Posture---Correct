import os
import cv2
import mediapipe as mp
import math
import tkinter as tk
import time
import threading
import winsound

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pose_landmarker.task")

options = PoseLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=VisionRunningMode.VIDEO
)

# Landmark indices
NOSE = 0
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
MIN_LANDMARK_VISIBILITY = 0.5

# Skeleton connections, just for drawing
POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (24, 26), (26, 28)
]

# --- Calibration settings ---
GET_READY_SECONDS = 5         # time to sit properly after pressing 'c'
CALIBRATION_SECONDS = 3       # how long readings are collected
MARGIN = 0.011                # slightly more movement beyond baseline before flagging bad posture
                              # smaller = more sensitive, larger = less sensitive
MAX_SPREAD = 0.05             # if readings vary more than this during calibration, you moved too much
MAX_BASELINE = None           # optional sanity limit (see notes). None = disabled

# --- Persistence settings ---
PERSISTENCE_SECONDS = 3       # how long bad posture must persist before alerting
ALERT_BEEP_DURATION_MS = 100
ALERT_BEEP_PAUSE_SECONDS = 0.1

UI_BORDER_COLOR = (45, 95, 60)       # olive green, in OpenCV's BGR format
NOTICE_TEXT_COLOR = (125, 220, 165)  # light olive green, in OpenCV's BGR format
UI_BORDER_THICKNESS = 8

def get_head_drop(landmarks):
    """Returns how far the nose has dropped relative to shoulder height."""
    nose_y = landmarks[NOSE].y
    left_shoulder_y = landmarks[LEFT_SHOULDER].y
    right_shoulder_y = landmarks[RIGHT_SHOULDER].y
    shoulder_avg_y = (left_shoulder_y + right_shoulder_y) / 2
    return nose_y - shoulder_avg_y  # more negative = head higher above shoulders (better posture)

def has_reliable_posture_landmarks(landmarks):
    """Avoid posture decisions when the face or either shoulder is poorly tracked."""
    return all(
        landmarks[index].visibility >= MIN_LANDMARK_VISIBILITY
        for index in (NOSE, LEFT_SHOULDER, RIGHT_SHOULDER)
    )

def draw_skeleton(frame, landmarks, w, h):
    for lm in landmarks:
        cx, cy = int(lm.x * w), int(lm.y * h)
        cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)
    for start_idx, end_idx in POSE_CONNECTIONS:
        x1, y1 = int(landmarks[start_idx].x * w), int(landmarks[start_idx].y * h)
        x2, y2 = int(landmarks[end_idx].x * w), int(landmarks[end_idx].y * h)
        cv2.line(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)

def play_alert(stop_event):
    while not stop_event.is_set():
        winsound.Beep(1000, ALERT_BEEP_DURATION_MS)
        stop_event.wait(ALERT_BEEP_PAUSE_SECONDS)

alert_thread = None
alert_stop_event = None

def start_alert():
    global alert_thread, alert_stop_event
    if alert_thread is None or not alert_thread.is_alive():
        alert_stop_event = threading.Event()
        alert_thread = threading.Thread(
            target=play_alert,
            args=(alert_stop_event,),
            daemon=True,
        )
        alert_thread.start()

def stop_alert():
    if alert_stop_event is not None:
        alert_stop_event.set()

notification_root = tk.Tk()
notification_root.withdraw()
notification_popup = tk.Toplevel(notification_root)
notification_popup.withdraw()
notification_popup.overrideredirect(True)
notification_popup.attributes("-topmost", True)
notification_popup.configure(bg="#F27336")

notification_content = tk.Frame(
    notification_popup,
    bg="#F27336",
    padx=18,
    pady=14,
)
notification_content.pack(fill="both", expand=True)
tk.Label(
    notification_content,
    text="POSTURE WARNING",
    font=("Segoe UI", 13, "bold"),
    fg="white",
    bg="#F27336",
    anchor="w",
).pack(fill="x")
tk.Label(
    notification_content,
    text="Please sit up straight to clear this alert.",
    font=("Segoe UI", 10),
    fg="white",
    bg="#F27336",
    anchor="w",
).pack(fill="x", pady=(5, 0))

notification_root.update_idletasks()
notification_width = 700
notification_height = 110
notification_x = notification_popup.winfo_screenwidth() - notification_width - 24
notification_popup.geometry(
    f"{notification_width}x{notification_height}+{notification_x}+24"
)

cap = cv2.VideoCapture(0)  # change to 1 if you're using an external webcam
if not cap.isOpened():
    notification_root.destroy()
    raise RuntimeError("Could not open webcam 0. Check the camera connection or try index 1.")

last_timestamp_ms = -1
session_start_ns = time.monotonic_ns()

# --- Calibration state ---
phase = "idle"             # idle -> countdown -> capturing -> idle
phase_start = None
calibration_samples = []
baseline = None
notice = ""                # message shown under the status line

# --- Bad posture tracking ---
bad_posture_start_time = None

with PoseLandmarker.create_from_options(options) as landmarker:
    while True:
        success, frame = cap.read()
        if not success:
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        elapsed_ms = (time.monotonic_ns() - session_start_ns) // 1_000_000
        timestamp_ms = max(last_timestamp_ms + 1, elapsed_ms)
        last_timestamp_ms = timestamp_ms

        result = landmarker.detect_for_video(mp_image, timestamp_ms)

        status_text = "No person detected"
        status_color = (200, 200, 200)
        alert_active = False

        if result.pose_landmarks:
            landmarks = result.pose_landmarks[0]
            h, w, _ = frame.shape
            now = time.monotonic()

            if not has_reliable_posture_landmarks(landmarks):
                bad_posture_start_time = None
                status_text = "Move face and shoulders into view"
                status_color = (255, 200, 0)
            else:
                head_drop = get_head_drop(landmarks)

                # ---- CALIBRATION: GET-READY COUNTDOWN ----
                if phase == "countdown":
                    remaining = GET_READY_SECONDS - (now - phase_start)
                    status_text = f"Sit upright... starting in {max(0, remaining):.0f}s"
                    status_color = (255, 200, 0)
                    if remaining <= 0:
                        phase = "capturing"
                        phase_start = now
                        calibration_samples = []

                # ---- CALIBRATION: CAPTURING READINGS ----
                elif phase == "capturing":
                    calibration_samples.append(head_drop)
                    remaining = CALIBRATION_SECONDS - (now - phase_start)
                    status_text = f"Calibrating... {max(0, math.ceil(remaining))}s"
                    status_color = (255, 200, 0)

                    if now - phase_start >= CALIBRATION_SECONDS:
                        spread = max(calibration_samples) - min(calibration_samples)
                        avg = sum(calibration_samples) / len(calibration_samples)

                        if spread > MAX_SPREAD:
                            notice = "Calibration failed: too much movement. Press C to retry."
                        elif MAX_BASELINE is not None and avg > MAX_BASELINE:
                            notice = "Calibration failed: posture looks slouched. Press C to retry."
                        else:
                            baseline = avg
                            notice = "Calibrated! Press C to recalibrate anytime."

                        print(f"Calibration result: avg={avg:.4f}, spread={spread:.4f}")
                        phase = "idle"

                # ---- NORMAL DETECTION PHASE ----
                else:
                    if baseline is None:
                        status_text = "Sit upright, then press C to calibrate"
                        status_color = (255, 200, 0)
                    elif head_drop > baseline + MARGIN:
                        if bad_posture_start_time is None:
                            bad_posture_start_time = now
                        elapsed_bad = now - bad_posture_start_time

                        if elapsed_bad >= PERSISTENCE_SECONDS:
                            status_text = "POOR POSTURE - Sit up straight!"
                            status_color = (0, 0, 255)  # red
                            alert_active = True
                        else:
                            status_text = "Checking..."
                            status_color = (0, 165, 255)  # orange
                    else:
                        bad_posture_start_time = None
                        status_text = "Good posture"
                        status_color = (0, 200, 0)  # green

            draw_skeleton(frame, landmarks, w, h)
        else:
            bad_posture_start_time = None

        if alert_active:
            start_alert()
            if not notification_popup.winfo_viewable():
                notification_popup.deiconify()
                notification_popup.lift()
                notification_popup.attributes("-topmost", True)
        else:
            stop_alert()
            notification_popup.withdraw()

        cv2.putText(frame, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
        cv2.putText(frame, notice, (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.75, NOTICE_TEXT_COLOR, 2)
        frame_height, frame_width = frame.shape[:2]
        cv2.rectangle(
            frame,
            (4, 4),
            (frame_width - 5, frame_height - 5),
            UI_BORDER_COLOR,
            UI_BORDER_THICKNESS,
        )
        cv2.imshow("PostureCorrect", frame)

        key = cv2.waitKey(1) & 0xFF
        notification_root.update()
        if key == ord('q'):
            break
        if key == ord('c') and phase == "idle":
            phase = "countdown"
            phase_start = time.monotonic()
            bad_posture_start_time = None
            notice = ""

stop_alert()
notification_root.destroy()
cap.release()   #.\venv\Scripts\python.exe .\main.py env variable establisher!
cv2.destroyAllWindows()    #in case venv dosent pop up .\venv\Scripts\activate