# calibration.py

import time


class CalibrationManager:
    def __init__(self, servo_controller, servo_channels, neutral_angles, offsets, servo_limits=None):
        self.servo_controller = servo_controller
        self.servo_channels = servo_channels
        self.neutral_angles = neutral_angles
        self.offsets = offsets
        self.servo_limits = servo_limits or {}

    def clamp_angle(self, name: str, angle: float) -> float:
        if name in self.servo_limits:
            low, high = self.servo_limits[name]
        else:
            low, high = 0, 180
        return max(low, min(high, angle))

    def get_neutral_pose(self):
        pose = {}
        for name, channel in self.servo_channels.items():
            base = self.neutral_angles[name]
            offset = self.offsets.get(name, 0)
            angle = self.clamp_angle(name, base + offset)
            pose[channel] = angle
        return pose

    def move_to_neutral(self, pause: float = 1.0):
        pose = self.get_neutral_pose()
        self.servo_controller.safe_neutral(pose)
        time.sleep(pause)

    def sweep_servo(self, channel, low=30, high=150, step=5, delay=0.05):
        for angle in range(low, high + 1, step):
            self.servo_controller.set_angle(channel, angle)
            time.sleep(delay)

        for angle in range(high, low - 1, -step):
            self.servo_controller.set_angle(channel, angle)
            time.sleep(delay)

    def test_all_servos(self, sweep_ranges=None, delay=0.05):
        sweep_ranges = sweep_ranges or {}

        for name, channel in self.servo_channels.items():
            low, high = sweep_ranges.get(name, self.servo_limits.get(name, (30, 150)))
            print(f"Testing {name} on channel {channel}: {low} -> {high}")
            self.sweep_servo(channel, low=low, high=high, step=5, delay=delay)
            self.move_to_neutral(pause=0.5)

    def print_neutral_pose(self):
        pose = self.get_neutral_pose()
        print("Neutral pose:")
        for channel, angle in pose.items():
            print(f"  channel {channel}: {angle}")