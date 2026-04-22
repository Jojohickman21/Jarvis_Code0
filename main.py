# main.py

import time
from config import SERVO_CHANNELS, NEUTRAL_ANGLES, SERVO_OFFSETS, SERVO_LIMITS
from servo_controller import ServoController
from calibration import CalibrationManager


def main():
    servos = ServoController(channels=16)
    calibration = CalibrationManager(
        servo_controller=servos,
        servo_channels=SERVO_CHANNELS,
        neutral_angles=NEUTRAL_ANGLES,
        offsets=SERVO_OFFSETS,
        servo_limits=SERVO_LIMITS,
    )

    print("Moving robot to neutral pose...")
    calibration.move_to_neutral()

    print("Calibration complete. Robot is ready.")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()