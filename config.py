# config.py

SERVO_CHANNELS = {
    "neck_yaw": 0,      # left/right
    "head_pitch": 1,    # up/down
    "left_arm": 2,
    "right_arm": 3,
}

NEUTRAL_ANGLES = {
    "neck_yaw": 90,
    "head_pitch": 90,
    "left_arm": 90,
    "right_arm": 90,
}

SERVO_OFFSETS = {
    "neck_yaw": 0,
    "head_pitch": 0,
    "left_arm": 0,
    "right_arm": 0,
}

SERVO_LIMITS = {
    "neck_yaw": (0, 180),
    "head_pitch": (30, 150),
    "left_arm": (20, 160),
    "right_arm": (20, 160),
}

CAMERA_INDEX = 0

ALARM_SOUND_PATH = "/home/luca/robot_assets/alarm.mp3"
SECURITY_PASSWORD = "1234"

SENTRY_ARM_DELAY = 10
SENTRY_SCAN_STEP = 30
SENTRY_PAUSE_SECONDS = 1.5

ALARM_NECK_SWING_AMPLITUDE = 35
ALARM_ARM_SWING_AMPLITUDE = 35
ALARM_SWING_DELAY = 0.06