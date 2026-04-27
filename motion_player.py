import time
from config import SERVO_CHANNELS, NEUTRAL_ANGLES


class MotionPlayer:
    def __init__(self, servo_controller):
        self.servo_controller = servo_controller

    def _apply_offset(self, pose):
        final = {}
        for name, delta in pose.items():
            base = NEUTRAL_ANGLES[name]
            final[name] = base + delta
        return final

    def _set_pose(self, pose: dict):
        pose = self._apply_offset(pose)

        pose_channels = {
            SERVO_CHANNELS[name]: angle
            for name, angle in pose.items()
        }
        self.servo_controller.set_pose(pose_channels)

    # ─────────────────────────────────────────────
    # SMOOTH MOVEMENT
    # ─────────────────────────────────────────────
    def _smooth_move(self, name, start, end, step=2, delay=0.01, fixed_pose=None):
        if start < end:
            rng = range(start, end, step)
        else:
            rng = range(start, end, -step)

        for val in rng:
            pose = {name: val}
            if fixed_pose:
                pose.update(fixed_pose)
            self._set_pose(pose)
            time.sleep(delay)

    # ─────────────────────────────────────────────
    # HAPPY (LEFT ARM FULL WAVE)
    # ─────────────────────────────────────────────
    def _happy(self):
        for _ in range(4):
            self._set_pose({
                "head_pitch": -5,
                "left_arm": +170,   # full up
                "right_arm": 0,
            })
            time.sleep(0.12)

            self._set_pose({
                "head_pitch": +5,
                "left_arm": -10,    # full down
                "right_arm": 0,
            })
            time.sleep(0.12)

    # ─────────────────────────────────────────────
    # ANGRY (FULL RANGE BOTH ARMS)
    # ─────────────────────────────────────────────
    def _angry(self):
        for _ in range(8):
            self._set_pose({
                "neck_yaw": -20,
                "head_pitch": +30,
                "left_arm": +170,
                "right_arm": +170,
            })
            time.sleep(0.06)

            self._set_pose({
                "neck_yaw": +20,
                "head_pitch": +20,
                "left_arm": -20,
                "right_arm": -20,
            })
            time.sleep(0.06)

    # ─────────────────────────────────────────────
    # SCARED (HEAD ONLY JITTER)
    # ─────────────────────────────────────────────
    def _scared(self):
        for _ in range(10):
            self._set_pose({
                "neck_yaw": -5,
                "head_pitch": +10,
            })
            time.sleep(0.05)

            self._set_pose({
                "neck_yaw": +5,
                "head_pitch": +15,
            })
            time.sleep(0.05)

    # ─────────────────────────────────────────────
    # SAD (FASTER SMOOTH "NO")
    # ─────────────────────────────────────────────
    def _sad(self):
        base_pitch = +40  # head down

        for _ in range(2):
            self._smooth_move(
                "neck_yaw",
                0,
                -30,
                fixed_pose={"head_pitch": base_pitch},
                delay=0.01   # 🔥 faster
            )

            self._smooth_move(
                "neck_yaw",
                -30,
                +30,
                fixed_pose={"head_pitch": base_pitch},
                delay=0.01
            )

            self._smooth_move(
                "neck_yaw",
                +30,
                0,
                fixed_pose={"head_pitch": base_pitch},
                delay=0.01
            )

    # ─────────────────────────────────────────────
    # DISGUSTED (HEAD ONLY)
    # ─────────────────────────────────────────────
    def _disgusted(self):
        for _ in range(3):
            self._set_pose({
                "neck_yaw": +30,
                "head_pitch": +20,
            })
            time.sleep(0.3)

            self._set_pose({
                "neck_yaw": -10,
                "head_pitch": +25,
            })
            time.sleep(0.3)

    # ─────────────────────────────────────────────
    # NEUTRAL
    # ─────────────────────────────────────────────
    def _neutral(self):
        self._set_pose({
            "neck_yaw": 0,
            "head_pitch": 0,
            "left_arm": 0,
            "right_arm": 0,
        })

    # ─────────────────────────────────────────────
    # MAIN ENTRY
    # ─────────────────────────────────────────────
    def play(self, personality: str):
        if personality in ["happy_excited", "rizz"]:
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