# config.py

SERVO_CHANNELS = {
    "neck_yaw": 0,      # left/right
    "head_pitch": 1,    # up/down
    "left_arm": 3,
    "right_arm": 2,
}

NEUTRAL_ANGLES = {
    "neck_yaw": 105,
    "head_pitch": 63,
    "left_arm": 10,
    "right_arm": 10,
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
    "left_arm": (10, 180),
    "right_arm": (10, 180),
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

# ─── Voice Assistant ────────────────────────────────────────────
WAKE_WORD = "jarvis"              # built-in Porcupine keyword (free)
RECORD_SECONDS_MAX = 3           # max recording length after wake word
SILENCE_THRESHOLD = 500           # RMS energy below this = silence
SILENCE_DURATION = 0.5            # seconds of silence to stop recording
SAMPLE_RATE = 48000              # 16kHz — required by Porcupine & Whisper
OPENAI_MODEL = "gpt-4o-mini"     # fast, cheap, great for conversation
DEFAULT_PERSONALITY = "happy_excited"
TEMP_AUDIO_PATH = "/tmp/jarvis_recording.wav"

# AUDIO / CAMERA CONFIG
# Speaker (USB audio device)
AUDIO_OUTPUT_DEVICE = "plughw:3,0"

# Microphone (use webcam mic — better quality usually)
AUDIO_INPUT_DEVICE = "plughw:2,0"

# Webcam
CAMERA_INDEX = 0