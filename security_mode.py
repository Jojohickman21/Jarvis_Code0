# security_mode.py (OPTIMIZED)

import cv2
import time
import threading
from config import SERVO_CHANNELS, CAMERA_INDEX


class SecuritySentry:
    def __init__(self, servo_controller):
        self.servo_controller = servo_controller
        self.running = False
        self.thread = None

        # Load face detector
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
        return True

    def is_armed(self):
        return self.running

    def status(self):
        return "ARMED" if self.running else "DISARMED"

    # ─────────────────────────────
    # CORE LOOP
    # ─────────────────────────────
    def _run(self):
        time.sleep(2)  # arm delay

        cap = cv2.VideoCapture(CAMERA_INDEX)

        # 🔥 SPEED FIX 1: low resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

        frame_count = 0

        # scan angles
        angles = list(range(60, 120, 10)) + list(range(120, 60, -10))

        while self.running:
            for angle in angles:
                if not self.running:
                    break

                # move neck
                self.servo_controller.set_angle(
                    SERVO_CHANNELS["neck_yaw"], angle
                )

                # 🔥 SPEED FIX 2: shorter delay
                time.sleep(0.3)

                # capture frame
                ret, frame = cap.read()
                if not ret:
                    continue

                frame_count += 1

                # 🔥 SPEED FIX 3: skip frames
                if frame_count % 3 != 0:
                    continue

                # 🔥 SPEED FIX 4: resize for faster detection
                small = cv2.resize(frame, (160, 120))

                # 🔥 SPEED FIX 5: grayscale
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

                faces = self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=4,
                    minSize=(30, 30),
                )

                if len(faces) > 0:
                    print("[SECURITY] HUMAN DETECTED")
                    self._trigger_alarm()
                    cap.release()
                    return

        cap.release()

    # ─────────────────────────────
    # ALARM BEHAVIOR
    # ─────────────────────────────
    def _trigger_alarm(self):
        print("[SECURITY] ALARM TRIGGERED")

        for _ in range(12):
            if not self.running:
                return

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