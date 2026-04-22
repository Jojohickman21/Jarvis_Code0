# security_mode.py

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import pygame

from config import (
    CAMERA_INDEX,
    NEUTRAL_ANGLES,
    SERVO_CHANNELS,
    SERVO_LIMITS,
    SERVO_OFFSETS,
    SECURITY_PASSWORD,
    ALARM_SOUND_PATH,
    SENTRY_ARM_DELAY,
    SENTRY_SCAN_STEP,
    SENTRY_PAUSE_SECONDS,
    ALARM_NECK_SWING_AMPLITUDE,
    ALARM_ARM_SWING_AMPLITUDE,
    ALARM_SWING_DELAY,
)


class SecuritySentry:
    def __init__(self, servo_controller):
        self.servo_controller = servo_controller
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._alarm_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._armed = False
        self._alarm_active = False

        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        pygame.mixer.init()
        self.alarm_path = Path(ALARM_SOUND_PATH)

    def is_armed(self) -> bool:
        with self._lock:
            return self._armed

    def is_alarm_active(self) -> bool:
        with self._lock:
            return self._alarm_active

    def status(self) -> str:
        with self._lock:
            if self._alarm_active:
                return "ALARM"
            if self._armed:
                return "ARMED / SCANNING"
            return "DISARMED"

    def arm(self):
        with self._lock:
            if self._armed or self._thread is not None:
                return
            self._armed = True
            self._alarm_active = False
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def disarm(self, password: str) -> bool:
        if password != SECURITY_PASSWORD:
            return False

        self._stop_event.set()
        self._stop_alarm()

        with self._lock:
            self._armed = False
            self._alarm_active = False
            self._thread = None
            self._alarm_thread = None

        self._return_to_neutral()
        return True

    def _neutral_angle(self, name: str) -> int:
        base = NEUTRAL_ANGLES[name]
        offset = SERVO_OFFSETS.get(name, 0)
        return base + offset

    def _clamp(self, name: str, angle: int) -> int:
        low, high = SERVO_LIMITS.get(name, (0, 180))
        return max(low, min(high, angle))

    def _set_servo(self, name: str, angle: int):
        channel = SERVO_CHANNELS[name]
        self.servo_controller.set_angle(channel, self._clamp(name, angle))

    def _return_to_neutral(self):
        self._set_servo("neck_yaw", self._neutral_angle("neck_yaw"))
        self._set_servo("head_pitch", self._neutral_angle("head_pitch"))
        self._set_servo("left_arm", self._neutral_angle("left_arm"))
        self._set_servo("right_arm", self._neutral_angle("right_arm"))

    def _capture_frame(self, cap: cv2.VideoCapture):
        ok, frame = cap.read()
        if not ok:
            return None
        return frame

    def _detect_face(self, frame) -> bool:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
        )
        return len(faces) > 0

    def _start_alarm_sound(self):
        with self._lock:
            self._alarm_active = True

        if self.alarm_path.exists():
            pygame.mixer.music.load(str(self.alarm_path))
            pygame.mixer.music.play(loops=-1)
        else:
            print(f"Alarm sound not found: {self.alarm_path}")

    def _stop_alarm(self):
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

    def _alarm_motion_loop(self):
        """
        Once alarmed, no long pauses.
        Neck sweeps rapidly side to side and arms flap up/down together.
        """
        neck_center = self._neutral_angle("neck_yaw")
        left_center = self._neutral_angle("left_arm")
        right_center = self._neutral_angle("right_arm")

        neck_low = self._clamp("neck_yaw", neck_center - ALARM_NECK_SWING_AMPLITUDE)
        neck_high = self._clamp("neck_yaw", neck_center + ALARM_NECK_SWING_AMPLITUDE)

        arms_up = self._clamp("left_arm", left_center - ALARM_ARM_SWING_AMPLITUDE)
        arms_down = self._clamp("left_arm", left_center + ALARM_ARM_SWING_AMPLITUDE)

        # Keep both arms moving together
        left_arm_up = arms_up
        left_arm_down = arms_down
        right_arm_up = self._clamp("right_arm", right_center - ALARM_ARM_SWING_AMPLITUDE)
        right_arm_down = self._clamp("right_arm", right_center + ALARM_ARM_SWING_AMPLITUDE)

        pose_cycle = [
            (neck_low, left_arm_up, right_arm_up),
            (neck_high, left_arm_down, right_arm_down),
        ]

        while not self._stop_event.is_set():
            for neck_angle, left_angle, right_angle in pose_cycle:
                if self._stop_event.is_set():
                    break
                self._set_servo("neck_yaw", neck_angle)
                self._set_servo("left_arm", left_angle)
                self._set_servo("right_arm", right_angle)
                time.sleep(ALARM_SWING_DELAY)

    def _scan_once(self, cap: cv2.VideoCapture) -> bool:
        """
        Returns True if a face is found.
        """
        neutral = self._neutral_angle("neck_yaw")
        low, high = SERVO_LIMITS.get("neck_yaw", (0, 180))

        # scan right
        for angle in range(neutral, high + 1, SENTRY_SCAN_STEP):
            if self._stop_event.is_set():
                return False
            self._set_servo("neck_yaw", angle)
            time.sleep(SENTRY_PAUSE_SECONDS)

            frame = self._capture_frame(cap)
            if frame is not None and self._detect_face(frame):
                return True

        # scan left
        for angle in range(high, low - 1, -SENTRY_SCAN_STEP):
            if self._stop_event.is_set():
                return False
            self._set_servo("neck_yaw", angle)
            time.sleep(SENTRY_PAUSE_SECONDS)

            frame = self._capture_frame(cap)
            if frame is not None and self._detect_face(frame):
                return True

        self._set_servo("neck_yaw", neutral)
        return False

    def _run(self):
        print("Sentry arming...")
        for _ in range(SENTRY_ARM_DELAY):
            if self._stop_event.is_set():
                self._cleanup()
                return
            time.sleep(1)

        cap = cv2.VideoCapture(CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

        try:
            self._return_to_neutral()

            while not self._stop_event.is_set():
                found = self._scan_once(cap)
                if found:
                    print("Human detected. Alarm triggered.")
                    self._start_alarm_sound()

                    self._alarm_thread = threading.Thread(
                        target=self._alarm_motion_loop,
                        daemon=True,
                    )
                    self._alarm_thread.start()

                    while not self._stop_event.is_set():
                        time.sleep(0.1)
                    break

        finally:
            cap.release()
            self._stop_alarm()
            self._cleanup()

    def _cleanup(self):
        with self._lock:
            self._armed = False
            self._alarm_active = False
            self._thread = None
            self._alarm_thread = None