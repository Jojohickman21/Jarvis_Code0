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
    # CORE LOOP (FIXED — keeps scanning)
    # ─────────────────────────────
    def _run(self):
        time.sleep(2)

        cap = cv2.VideoCapture(CAMERA_INDEX)

        frame_count = 0
        angles = list(range(60, 120, 10)) + list(range(120, 60, -10))

        while self.running:
            for angle in angles:
                if not self.running:
                    break

                # ✅ KEEP HEAD SCANNING (FIXED)
                self.servo_controller.set_angle(
                    SERVO_CHANNELS["neck_yaw"], angle
                )

                time.sleep(0.4)

                ret, frame = cap.read()
                if not ret:
                    continue

                frame_count += 1
                if frame_count % 3 != 0:
                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                faces = self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=4,
                    minSize=(30, 30),
                )

                if len(faces) > 0:
                    print("[SECURITY] HUMAN DETECTED")

                    self._start_alarm()

                    # 🔥 run alarm behavior WITHOUT killing scanning loop
                    self._alarm_burst()

        cap.release()

    # ─────────────────────────────
    # ALARM AUDIO (FIXED — no bash loop)
    # ─────────────────────────────
    def _start_alarm(self):
        if self.alarm_process is None:
            print("[SECURITY] STARTING ALARM AUDIO")

            self.alarm_process = subprocess.Popen([
                "aplay",
                "-D", AUDIO_OUTPUT_DEVICE,
                ALARM_SOUND_PATH
            ])

    # ─────────────────────────────
    # ANGRY MOTION BURST (non-blocking scanning)
    # ─────────────────────────────
    def _alarm_burst(self):
        print("[SECURITY] ALARM BURST")

        for _ in range(3):
            if not self.running:
                break

            # 🔊 restart sound if it ended
            if self.alarm_process and self.alarm_process.poll() is not None:
                self.alarm_process = None
                self._start_alarm()

            if self.motion_player:
                self.motion_player.play("angry")
            else:
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