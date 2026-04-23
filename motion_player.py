# motion_player.py

import time
from config import SERVO_CHANNELS


class MotionPlayer:
    def __init__(self, servo_controller):
        self.servo_controller = servo_controller

    def _set_pose(self, pose: dict):
        pose_channels = {
            SERVO_CHANNELS[name]: angle
            for name, angle in pose.items()
        }
        self.servo_controller.set_pose(pose_channels)

    # ─────────────────────────────────────────────
    # HAPPY (bouncy + playful)
    # ─────────────────────────────────────────────
    def _happy(self):
        for _ in range(6):
            self._set_pose({
                "neck_yaw": 80,
                "head_pitch": 85,
                "left_arm": 70,
                "right_arm": 70,
            })
            time.sleep(0.12)

            self._set_pose({
                "neck_yaw": 100,
                "head_pitch": 95,
                "left_arm": 110,
                "right_arm": 110,
            })
            time.sleep(0.12)

    # ─────────────────────────────────────────────
    # ANGRY (fast + aggressive)
    # ─────────────────────────────────────────────
    def _angry(self):
        for _ in range(10):
            self._set_pose({
                "neck_yaw": 70,
                "head_pitch": 110,
                "left_arm": 50,
                "right_arm": 50,
            })
            time.sleep(0.07)

            self._set_pose({
                "neck_yaw": 110,
                "head_pitch": 100,
                "left_arm": 130,
                "right_arm": 130,
            })
            time.sleep(0.07)

    # ─────────────────────────────────────────────
    # SCARED (rapid jitter)
    # ─────────────────────────────────────────────
    def _scared(self):
        for _ in range(12):
            self._set_pose({
                "neck_yaw": 85,
                "head_pitch": 70,
                "left_arm": 120,
                "right_arm": 120,
            })
            time.sleep(0.05)

            self._set_pose({
                "neck_yaw": 95,
                "head_pitch": 75,
                "left_arm": 110,
                "right_arm": 110,
            })
            time.sleep(0.05)

    # ─────────────────────────────────────────────
    # SAD (slow droop)
    # ─────────────────────────────────────────────
    def _sad(self):
        for _ in range(3):
            self._set_pose({
                "neck_yaw": 90,
                "head_pitch": 120,
                "left_arm": 130,
                "right_arm": 130,
            })
            time.sleep(0.6)

            self._set_pose({
                "neck_yaw": 90,
                "head_pitch": 115,
                "left_arm": 120,
                "right_arm": 120,
            })
            time.sleep(0.6)

    # ─────────────────────────────────────────────
    # DISGUSTED (pull away + tilt)
    # ─────────────────────────────────────────────
    def _disgusted(self):
        for _ in range(4):
            self._set_pose({
                "neck_yaw": 110,
                "head_pitch": 100,
                "left_arm": 90,
                "right_arm": 90,
            })
            time.sleep(0.25)

            self._set_pose({
                "neck_yaw": 70,
                "head_pitch": 95,
                "left_arm": 85,
                "right_arm": 85,
            })
            time.sleep(0.25)

    # ─────────────────────────────────────────────
    # NEUTRAL (reset)
    # ─────────────────────────────────────────────
    def _neutral(self):
        self._set_pose({
            "neck_yaw": 90,
            "head_pitch": 90,
            "left_arm": 90,
            "right_arm": 90,
        })

    # ─────────────────────────────────────────────
    # MAIN ENTRY
    # ─────────────────────────────────────────────
    def play(self, personality: str):
        if personality == "happy_excited":
            self._happy()
        elif personality == "angry":
            self._angry()
        elif personality == "scared":
            self._scared()
        elif personality == "sad_tired":
            self._sad()
        elif personality == "disgusted":
            self._disgusted()
        else:
            self._neutral()