import cv2
import time
import threading
import subprocess

from config import SERVO_CHANNELS, CAMERA_INDEX, AUDIO_OUTPUT_DEVICE, ALARM_SOUND_PATH


class SecuritySentry:
    def __init__(self, servo_controller, motion_player=None):
        self.servo_controller = servo_controller
        self.motion_player = motion_player

        self.running = False
        self.thread = None
        self.alarm_process = None

        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

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

        if self.alarm_process:
            self.alarm_process.terminate()
            self.alarm_process = None

        return True

    def is_armed(self):
        return self.running

    def status(self):
        return "ALARM" if self.alarm_process else ("ARMED" if self.running else "DISARMED")

    # ─────────────────────────────
    def _run(self):
        time.sleep(2)

        cap = cv2.VideoCapture(CAMERA_INDEX)

        while self.running:
            ret, frame = cap.read()
            if not ret:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30)
            )

            if len(faces) > 0:
                print("[SECURITY] HUMAN DETECTED")

                self._start_alarm()
                self._alarm_loop()

        cap.release()

    # ─────────────────────────────
    def _start_alarm(self):
        if self.alarm_process is None:
            print("[SECURITY] STARTING ALARM AUDIO")

            # 🔥 simple + reliable playback
            self.alarm_process = subprocess.Popen([
                "aplay",
                "-D", AUDIO_OUTPUT_DEVICE,
                ALARM_SOUND_PATH
            ])

    # ─────────────────────────────
    def _alarm_loop(self):
        print("[SECURITY] ALARM LOOP ACTIVE")

        while self.running:

            # 🔊 restart sound if finished
            if self.alarm_process and self.alarm_process.poll() is not None:
                self.alarm_process = None
                self._start_alarm()

            # 🔥 FORCE ANGRY MOTION
            if self.motion_player:
                print("[DEBUG] PLAYING ANGRY MOTION")
                self.motion_player.play("angry")

            time.sleep(0.1)