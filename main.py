# main.py — JARVIS Desktop Assistant
#
# Starts the voice assistant and the web dashboard on separate threads.
# Say "Jarvis" to interact. Use the dashboard to switch personalities.

import threading
import time

from config import (
    DEFAULT_PERSONALITY,
    SERVO_CHANNELS,
    NEUTRAL_ANGLES,
    SERVO_OFFSETS,
    SERVO_LIMITS,
)

# ── Hardware imports (graceful fallback for non-Pi machines) ────
try:
    from servo_controller import ServoController
    from calibration import CalibrationManager
    from motion_player import MotionPlayer

    HAS_SERVOS = True
except ImportError:
    HAS_SERVOS = False
    print("[WARN] Servo hardware not available — running in voice-only mode.")


def main():
    # ── Set up servos (if on a Raspberry Pi) ──────────────────
    servos = None
    motion_player = None

    if HAS_SERVOS:
        servos = ServoController(channels=16)
        calibration = CalibrationManager(
            servo_controller=servos,
            servo_channels=SERVO_CHANNELS,
            neutral_angles=NEUTRAL_ANGLES,
            offsets=SERVO_OFFSETS,
            servo_limits=SERVO_LIMITS,
        )
        motion_player = MotionPlayer(servos)

        print("Moving robot to neutral pose...")
        calibration.move_to_neutral()
        print("Calibration complete.")

    # ── Launch voice assistant ────────────────────────────────
    from assistant import VoiceAssistant

    assistant = VoiceAssistant(motion_player=motion_player)

    # ── Launch web dashboard in background ────────────────────
    try:
        from robot_dashboard import create_app

        app = create_app(
            servo_controller=servos,
            motion_player=motion_player,
            assistant=assistant,
        )

        dashboard_thread = threading.Thread(
            target=lambda: app.run(host="0.0.0.0", port=5000, debug=False),
            daemon=True,
        )
        dashboard_thread.start()
        print("[INFO] Dashboard running at http://0.0.0.0:5000")
    except Exception as exc:
        print(f"[WARN] Dashboard failed to start: {exc}")

    # ── Run the voice loop (blocking) ─────────────────────────
    assistant.run()


if __name__ == "__main__":
    main()