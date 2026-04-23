# robot_dashboard.py — Web control panel for JARVIS
#
# Serves a mobile-friendly dashboard for:
#   - Switching personality (live, affects voice assistant)
#   - Triggering servo motions
#   - Arming/disarming security sentry mode
#
# Usage:
#   from robot_dashboard import create_app
#   app = create_app(servo_controller, motion_player, assistant)
#   app.run(host="0.0.0.0", port=5000)

from __future__ import annotations

import threading
from typing import Optional

from flask import Flask, request, redirect, url_for, render_template_string

from config import SERVO_CHANNELS, NEUTRAL_ANGLES, SERVO_OFFSETS, SERVO_LIMITS


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def create_app(
    servo_controller=None,
    motion_player=None,
    assistant=None,
):
    """
    Factory that builds the Flask app.
    Accepts shared objects so the dashboard can control the assistant.
    """

    app = Flask(__name__)

    # ── Optional hardware ─────────────────────────────────────
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
        if sentry and sentry.status() != "DISARMED":
            return f"{base} | Security: {sentry.status()}"
        return base

    # ── HTML template ─────────────────────────────────────────

    HTML_PAGE = """
<!doctype html>
<html>
<head>
    <title>JARVIS Control Panel</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #0f0f13;
            color: #e0e0e6;
            padding: 20px;
            min-height: 100vh;
        }

        h1 {
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(135deg, #4fc3f7, #ab47bc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 6px;
        }

        .subtitle {
            font-size: 13px;
            color: #888;
            margin-bottom: 20px;
        }

        .card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            padding: 18px;
            margin-bottom: 16px;
            backdrop-filter: blur(10px);
        }

        .card h3 {
            font-size: 14px;
            color: #aaa;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
        }

        .status-bar {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 16px;
            background: rgba(79, 195, 247, 0.08);
            border: 1px solid rgba(79, 195, 247, 0.15);
            border-radius: 10px;
            margin-bottom: 16px;
            font-size: 14px;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #4fc3f7;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 10px;
        }

        button {
            width: 100%;
            padding: 14px 12px;
            font-size: 14px;
            font-weight: 600;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
            color: white;
        }

        .btn-personality {
            background: rgba(171, 71, 188, 0.2);
            border: 1px solid rgba(171, 71, 188, 0.3);
            color: #ce93d8;
        }
        .btn-personality:hover {
            background: rgba(171, 71, 188, 0.35);
            transform: translateY(-1px);
        }
        .btn-personality.active {
            background: rgba(171, 71, 188, 0.5);
            border-color: #ab47bc;
            color: white;
            box-shadow: 0 0 12px rgba(171, 71, 188, 0.3);
        }

        .btn-motion {
            background: rgba(79, 195, 247, 0.15);
            border: 1px solid rgba(79, 195, 247, 0.25);
            color: #81d4fa;
        }
        .btn-motion:hover {
            background: rgba(79, 195, 247, 0.3);
            transform: translateY(-1px);
        }

        .btn-neutral {
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.15);
            color: #bbb;
        }
        .btn-neutral:hover { background: rgba(255,255,255,0.15); }

        .btn-danger {
            background: rgba(239, 83, 80, 0.2);
            border: 1px solid rgba(239, 83, 80, 0.3);
            color: #ef9a9a;
        }
        .btn-danger:hover { background: rgba(239, 83, 80, 0.35); }

        .btn-secondary {
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.12);
            color: #aaa;
            width: auto;
            padding: 12px 20px;
        }

        input[type="password"] {
            width: 100%;
            padding: 12px;
            font-size: 14px;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.05);
            color: #e0e0e6;
        }
        input[type="password"]::placeholder { color: #666; }

        .security-row {
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 10px;
            align-items: center;
            margin-top: 10px;
        }

        .tip {
            font-size: 12px;
            color: #555;
            margin-top: 16px;
            line-height: 1.6;
        }

        form { margin: 0; }
    </style>
</head>
<body>
    <h1>JARVIS</h1>
    <p class="subtitle">Desktop Assistant Control Panel</p>

    <div class="status-bar">
        <div class="status-dot"></div>
        <span>{{ status }}</span>
    </div>

    <!-- Personality Switcher -->
    <div class="card">
        <h3>🎭 Personality</h3>
        <div class="grid">
            {% for key, profile in personalities.items() %}
            <form method="post" action="/personality/{{ key }}">
                <button type="submit"
                        class="btn-personality {{ 'active' if key == current_personality else '' }}">
                    {{ profile.display_name }}
                </button>
            </form>
            {% endfor %}
        </div>
    </div>

    <!-- Motion Controls -->
    <div class="card">
        <h3>🦾 Motions</h3>
        <div class="grid">
            <form method="post" action="/action/neutral">
                <button type="submit" class="btn-neutral">Neutral</button>
            </form>
            {% for key, profile in personalities.items() %}
            <form method="post" action="/action/{{ key }}">
                <button type="submit" class="btn-motion">{{ profile.display_name }}</button>
            </form>
            {% endfor %}
            <form method="post" action="/action/test_all_servos">
                <button type="submit" class="btn-motion">Test All</button>
            </form>
        </div>
    </div>

    <!-- Security -->
    <div class="card">
        <h3>🔒 Security</h3>
        <div class="grid" style="margin-bottom: 10px;">
            <form method="post" action="/security/arm">
                <button type="submit" class="btn-danger">Arm Sentry</button>
            </form>
        </div>
        <form method="post" action="/security/disarm">
            <div class="security-row">
                <input type="password" name="password" placeholder="Disarm password">
                <button type="submit" class="btn-secondary">Disarm</button>
            </div>
        </form>
    </div>

    <div class="tip">
        Say <strong>"Jarvis"</strong> to talk.
        Switch personalities here — the voice changes in real time.
    </div>
</body>
</html>
"""

    # ── Routes ────────────────────────────────────────────────

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
            ok = assistant.set_personality(name)
            if ok:
                set_status(f"Personality → {name}")
            else:
                set_status(f"Unknown personality: {name}")
        return redirect(url_for("index"))
   
    @app.route("/action/<name>", methods=["POST"])
    def action(name):
        valid = {
            "neutral", "happy_excited", "angry",
            "scared", "sad_tired", "disgusted",
            "test_all_servos",
        }
        if name not in valid:
            return redirect(url_for("index"))

        def _run():
            print(f"[DEBUG] Running action: {name}")
            with action_lock:
                if sentry and sentry.is_armed():
                    set_status("Disarm security first")
                    return
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
            if sentry.is_armed():
                set_status("Already armed")
            else:
                sentry.arm()
                set_status("Arming... wait 10s")
        else:
            set_status("Security not available")
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


# ── Standalone mode (if run directly) ─────────────────────────

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)