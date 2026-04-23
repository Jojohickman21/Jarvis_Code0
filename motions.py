# motions.py

from config import NEUTRAL_ANGLES, SERVO_OFFSETS, SERVO_LIMITS

SERVO_NAMES = ["neck_yaw", "head_pitch", "left_arm", "right_arm"]


def clamp_angle(name: str, angle: float) -> float:
    low, high = SERVO_LIMITS.get(name, (0, 180))
    return max(low, min(high, angle))


def build_pose(deltas: dict) -> dict:
    """
    Build an absolute pose from neutral angles + offsets + relative deltas.

    This means:
    - if you recalibrate neutral angles, motions follow automatically
    - if limits change, poses are clamped safely
    """
    pose = {}

    for name in SERVO_NAMES:
        base = NEUTRAL_ANGLES[name]
        offset = SERVO_OFFSETS.get(name, 0)
        delta = deltas.get(name, 0)

        angle = base + offset + delta
        pose[name] = clamp_angle(name, angle)

    return pose


MOTION_DEFINITIONS = {
    "happy_excited": {
        "loops": 2,
        "steps": 16,
        "start_delta": {
            "neck_yaw": 0,
            "head_pitch": 0,
            "left_arm": 0,
            "right_arm": 0,
        },
        "end_delta": {
            "neck_yaw": 20,
            "head_pitch": -10,
            "left_arm": -30,
            "right_arm": -30,
        },
    },

    "angry": {
        "loops": 2,
        "steps": 12,
        "start_delta": {
            "neck_yaw": 0,
            "head_pitch": 5,
            "left_arm": 0,
            "right_arm": 0,
        },
        "end_delta": {
            "neck_yaw": -15,
            "head_pitch": 10,
            "left_arm": -35,
            "right_arm": -35,
        },
    },

    "scared": {
        "loops": 2,
        "steps": 14,
        "start_delta": {
            "neck_yaw": 0,
            "head_pitch": 0,
            "left_arm": 0,
            "right_arm": 0,
        },
        "end_delta": {
            "neck_yaw": -20,
            "head_pitch": -15,
            "left_arm": 25,
            "right_arm": 25,
        },
    },

    "sad_tired": {
        "loops": 2,
        "steps": 18,
        "start_delta": {
            "neck_yaw": 0,
            "head_pitch": 0,
            "left_arm": 0,
            "right_arm": 0,
        },
        "end_delta": {
            "neck_yaw": 0,
            "head_pitch": 15,
            "left_arm": 30,
            "right_arm": 30,
        },
    },

    "disgusted": {
        "loops": 2,
        "steps": 14,
        "start_delta": {
            "neck_yaw": 0,
            "head_pitch": 0,
            "left_arm": 0,
            "right_arm": 0,
        },
        "end_delta": {
            "neck_yaw": 15,
            "head_pitch": 10,
            "left_arm": -15,
            "right_arm": -15,
        },
    },
}


PERSONALITY_MOTIONS = {
    name: {
        "loops": motion["loops"],
        "steps": motion["steps"],
        "start_pose": build_pose(motion["start_delta"]),
        "end_pose": build_pose(motion["end_delta"]),
    }
    for name, motion in MOTION_DEFINITIONS.items()
}