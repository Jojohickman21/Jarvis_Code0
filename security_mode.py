# security_mode.py (FINAL OPTIMIZED)

import cv2
import time
import threading
import subprocess
from config import SERVO_CHANNELS, CAMERA_INDEX


class SecuritySentry:
    def __init__(self, servo_controller):
        self.servo_controller = servo_controller
        self.running = False
        self.thread = None
        self.alarm_process = None

        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    # ─────────────────────────────
    # PUBLIC API
    # ─────────────────────────────
    def arm(self):
        if self.running:
            return

        print("[SECURITY] Arming...")
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def disarm(self, password):
        print("[SECURITY] Disarmed")
        self.running = False

        # 🔊 Stop alarm audio
        if self.alarm_process:
            self.alarm_process.terminate()
            self.alarm_process = None

        return True

    def is_armed(self):
        return self.running

    def status(self):
        return "ALARM" if self.alarm_process else ("ARMED" if self.running else "DISARMED")

    # ─────────────────────────────
    # CORE LOOP
    # ─────────────────────────────
    def _run(self):
        time.sleep(2)

        cap = cv2.VideoCapture(CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

        frame_count = 0
        angles = list(range(60, 120, 10)) + list(range(120, 60, -10))

        while self.running:
            for angle in angles:
                if not self.running:
                    break

                # move neck
                self.servo_controller.set_angle(
                    SERVO_CHANNELS["neck_yaw"], angle
                )

                time.sleep(0.5)

                ret, frame = cap.read()
                if not ret:
                    continue

                frame_count += 1
                if frame_count % 3 != 0:
                    continue

                small = cv2.resize(frame, (160, 120))
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

                faces = self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=4,
                    minSize=(30, 30),
                )

                if len(faces) > 0:
                    print("[SECURITY] HUMAN DETECTED")
                    self._start_alarm()
                    self._alarm_loop()

        cap.release()

    # ─────────────────────────────
    # ALARM CONTROL
    # ─────────────────────────────
    def _start_alarm(self):
        if self.alarm_process is None:
            print("[SECURITY] STARTING ALARM AUDIO")

            # 🔊 Digital volume boost with -f
            self.alarm_process = subprocess.Popen([
                "mpg123",
                "-a", "hw:3,0",
                "-f", "5000",      # 🔥 volume boost
                "--loop", "-1",    # 🔥 infinite loop
                "/home/luca/Jarvis_Code0/alarm.mp3"
            ])

    def _alarm_loop(self):
        print("[SECURITY] ALARM LOOP ACTIVE")

        while self.running:
            # aggressive motion
            self.servo_controller.set_pose({
                SERVO_CHANNELS["left_arm"]: 50,
                SERVO_CHANNELS["right_arm"]: 50,
                SERVO_CHANNELS["neck_yaw"]: 70,
            })
            time.sleep(0.07)

            self.servo_controller.set_pose({
                SERVO_CHANNELS["left_arm"]: 130,
                SERVO_CHANNELS["right_arm"]: 130,
                SERVO_CHANNELS["neck_yaw"]: 110,
            })
            time.sleep(0.07)