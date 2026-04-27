# robot_dashboard.py — Web control panel for JARVIS

from __future__ import annotations

import threading
from typing import Optional

from flask import Flask, request, redirect, url_for, render_template_string

from config import SERVO_CHANNELS, NEUTRAL_ANGLES, SERVO_OFFSETS, SERVO_LIMITS


def create_app(
    servo_controller=None,
    motion_player=None,
    assistant=None,
):
    app = Flask(__name__)

    calibration = None
    sentry = None

    if servo_controller is not None:
        from calibration import CalibrationManager

        calibration = CalibrationManager(
            servo_controller=servo_controller,
            servo_channels=SERVO_CHANNELS,
            neutral_angles=NEUTRAL_ANGLES,
            offsets=SERVO_OFFSETS,
            servo_limits=SERVO_LIMITS,
        )

        try:
            from security_mode import SecuritySentry
            sentry = SecuritySentry(servo_controller)
        except Exception:
            sentry = None

    action_lock = threading.Lock()
    status_lock = threading.Lock()
    ui_status = {"msg": "Idle"}

    def set_status(message: str):
        with status_lock:
            ui_status["msg"] = message

    def get_status() -> str:
        with status_lock:
            base = ui_status["msg"]

        if assistant:
            listen_state = "ON" if assistant.listening_enabled else "OFF"
            base = f"{base} | Listening: {listen_state}"

        if sentry and sentry.status() != "DISARMED":
            return f"{base} | Security: {sentry.status()}"

        return base

    HTML_PAGE = """
<!doctype html>
<html>
<head>
<title>JARVIS Control Panel</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { font-family: Arial; background: #111; color: #eee; padding: 20px; }
button { padding: 12px; margin: 5px; border-radius: 8px; border: none; cursor: pointer; }
.btn { background: #444; color: white; }
.btn-danger { background: #aa3333; }
.btn-success { background: #2e7d32; }
.btn-motion { background: #1976d2; }
</style>
</head>
<body>

<h2>JARVIS Control Panel</h2>

<p><strong>Status:</strong> {{ status }}</p>

<h3>🎤 Voice Control</h3>
<form method="post" action="/listening/on">
    <button class="btn-success">Start Listening</button>
</form>
<form method="post" action="/listening/off">
    <button class="btn-danger">Stop Listening</button>
</form>

<h3>🎭 Personality</h3>
{% for key, profile in personalities.items() %}
<form method="post" action="/personality/{{ key }}">
    <button class="btn">{{ profile.display_name }}</button>
</form>
{% endfor %}

<h3>🦾 Motions</h3>
<form method="post" action="/action/neutral">
    <button class="btn">Neutral</button>
</form>

{% for key, profile in personalities.items() %}
<form method="post" action="/action/{{ key }}">
    <button class="btn-motion">{{ profile.display_name }}</button>
</form>
{% endfor %}

<form method="post" action="/action/test_all_servos">
    <button class="btn-motion">Test All Servos</button>
</form>

<h3>🔒 Security</h3>
<form method="post" action="/security/arm">
    <button class="btn-danger">Arm</button>
</form>

<form method="post" action="/security/disarm">
    <input type="password" name="password" placeholder="Password">
    <button class="btn">Disarm</button>
</form>

</body>
</html>
"""

    @app.route("/", methods=["GET"])
    def index():
        personalities = {}
        current = "unknown"
        if assistant:
            personalities = assistant.personalities
            current = assistant.personality_name

        return render_template_string(
            HTML_PAGE,
            status=get_status(),
            personalities=personalities,
            current_personality=current,
        )

    @app.route("/personality/<name>", methods=["POST"])
    def switch_personality(name):
        if assistant:
            assistant.set_personality(name)
            set_status(f"Personality → {name}")
        return redirect(url_for("index"))

    @app.route("/listening/on", methods=["POST"])
    def listening_on():
        if assistant:
            assistant.set_listening(True)
            set_status("Listening ON")
        return redirect(url_for("index"))

    @app.route("/listening/off", methods=["POST"])
    def listening_off():
        if assistant:
            assistant.set_listening(False)
            set_status("Listening OFF")
        return redirect(url_for("index"))

    @app.route("/action/<name>", methods=["POST"])
    def action(name):
        def _run():
            with action_lock:
                set_status(f"Running {name}")
                try:
                    if name == "neutral" and calibration:
                        calibration.move_to_neutral()
                    elif name == "test_all_servos" and calibration:
                        calibration.test_all_servos()
                    elif motion_player:
                        motion_player.play(name)
                    set_status(f"Finished {name}")
                except Exception as exc:
                    set_status(f"Error: {exc}")

        threading.Thread(target=_run, daemon=True).start()
        return redirect(url_for("index"))

    @app.route("/security/arm", methods=["POST"])
    def security_arm():
        if sentry:
            sentry.arm()
            set_status("Arming security")
        return redirect(url_for("index"))

    @app.route("/security/disarm", methods=["POST"])
    def security_disarm():
        if sentry:
            pwd = request.form.get("password", "")
            if sentry.disarm(pwd):
                set_status("Disarmed")
            else:
                set_status("Wrong password")
        return redirect(url_for("index"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)