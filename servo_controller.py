from adafruit_servokit import ServoKit


class ServoController:
    def __init__(self, channels=16):
        self.kit = ServoKit(channels=channels)

    def set_angle(self, channel, angle):
        angle = max(0, min(180, angle))
        print(f"[SERVO] Channel {channel} → {angle}")
        self.kit.servo[channel].angle = angle

    def set_pose(self, pose):
        for channel, angle in pose.items():
            self.set_angle(channel, angle)

    def safe_neutral(self, mapping):
        self.set_pose(mapping)