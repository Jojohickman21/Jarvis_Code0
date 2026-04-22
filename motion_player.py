# motion_player.py

import time
from motions import PERSONALITY_MOTIONS


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class MotionPlayer:
    def __init__(self, servo_controller):
        self.servo_controller = servo_controller

    def _interpolate_pose(self, start_pose: dict, end_pose: dict, t: float) -> dict:
        """
        Interpolates between two poses.
        Uses the union of keys so the code stays resilient if poses change later.
        """
        all_names = set(start_pose) | set(end_pose)
        pose = {}

        for name in all_names:
            start_angle = start_pose.get(name, end_pose.get(name, 90))
            end_angle = end_pose.get(name, start_pose.get(name, 90))
            pose[name] = lerp(start_angle, end_angle, t)

        return pose

    def _play_pose_transition(self, start_pose: dict, end_pose: dict, steps: int, delay: float):
        if steps <= 0:
            self.servo_controller.set_pose(end_pose)
            return

        for i in range(steps + 1):
            t = i / steps
            pose = self._interpolate_pose(start_pose, end_pose, t)
            self.servo_controller.set_pose(pose)
            time.sleep(delay)

    def play(self, personality: str, step_delay: float = 0.03):
        """
        Plays one of the prebuilt motions from motions.py.
        Falls back to happy_excited if the requested motion is missing.
        """
        if personality not in PERSONALITY_MOTIONS:
            personality = "happy_excited"

        motion = PERSONALITY_MOTIONS[personality]
        loops = motion["loops"]
        steps = motion["steps"]
        start_pose = motion["start_pose"]
        end_pose = motion["end_pose"]

        for _ in range(loops):
            self._play_pose_transition(start_pose, end_pose, steps, step_delay)
            self._play_pose_transition(end_pose, start_pose, steps, step_delay)