# robot_dashboard.py

import threading
from flask import Flask, request, redirect, url_for, render_template_string

from config import SERVO_CHANNELS, NEUTRAL_ANGLES, SERVO_OFFSETS, SERVO_LIMITS
from servo_controller import ServoController
from calibration import CalibrationManager
from motion_player import MotionPlayer
from security_mode import SecuritySentry

app = Flask(__name__)

servos = ServoController(channels=16)
calibration = CalibrationManager(
    servo_controller=servos,
    servo_channels=SERVO_CHANNELS,
    neutral_angles=NEUTRAL_ANGLES,
    offsets=SERVO_OFFSETS,
    servo_limits=SERVO_LIMITS,
)
motion_player = MotionPlayer(servos)
sentry = SecuritySentry(servos)

action_lock = threading.Lock()
status_lock = threading.Lock()

ui_status = "Idle"


def set_status(message: str):
    global ui_status
    with status_lock:
        ui_status = message


def get_status() -> str:
    with status_lock:
        base = ui_status

    security = sentry.status()

    if security == "DISARMED":
        return base

    return f"{base} | Security: {security}"


HTML_PAGE = """
<!doctype html>
<html>
<head>
    <title>Robot Test Panel</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 24px;
            background: #f4f4f4;
            color: #222;
        }
        h1 { margin-bottom: 8px; }
        .status {
            padding: 12px 16px;
            background: white;
            border-radius: 10px;
            margin-bottom: 18px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
            margin-bottom: 18px;
        }
        form {
            margin: 0;
        }
        button {
            width: 100%;
            padding: 16px;
            font-size: 16px;
            border: none;
            border-radius: 12px;
            background: #2d6cdf;
            color: white;
            cursor: pointer;
        }
        button:hover {
            background: #2457b5;
        }
        .secondary {
            background: #666;
        }
        .warning {
            background: #c97a00;
        }
        .danger {
            background: #b3261e;
        }
        .small {
            font-size: 14px;
            color: #555;
            margin-top: 18px;
            line-height: 1.5;
        }
        .security-box {
            background: white;
            padding: 16px;
            border-radius: 12px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
            margin-bottom: 18px;
        }
        .security-row {
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 12px;
            align-items: center;
            margin-top: 10px;
        }
        input[type="password"] {
            width: 100%;
            padding: 14px 12px;
            font-size: 15px;
            border-radius: 10px;
            border: 1px solid #ccc;
            box-sizing: border-box;
        }
    </style>
</head>
<body>
    <h1>Robot Test Panel</h1>

    <div class="status"><strong>Status:</strong> {{ status }}</div>

    <div class="security-box">
        <h3 style="margin-top:0;">Security System</h3>

        <div class="grid" style="margin-bottom: 10px;">
            <form method="post" action="/security/arm">
                <button type="submit" class="danger">Arm Sentry Mode</button>
            </form>
        </div>

        <form method="post" action="/security/disarm">
            <div class="security-row">
                <input type="password" name="password" placeholder="Enter disarm password">
                <button type="submit" class="secondary" style="width:auto;">Disarm</button>
            </div>
        </form>
    </div>

    <div class="grid">
        <form method="post" action="/action/neutral">
            <button type="submit" class="secondary">Move to Neutral</button>
        </form>

        <form method="post" action="/action/happy_excited">
            <button type="submit">Happy / Excited</button>
        </form>

        <form method="post" action="/action/angry">
            <button type="submit">Angry</button>
        </form>

        <form method="post" action="/action/scared">
            <button type="submit">Scared</button>
        </form>

        <form method="post" action="/action/sad_tired">
            <button type="submit">Sad / Tired</button>
        </form>

        <form method="post" action="/action/disgusted">
            <button type="submit">Disgusted</button>
        </form>

        <form method="post" action="/action/test_all_servos">
            <button type="submit" class="warning">Test All Servos</button>
        </form>
    </div>

    <div class="small">
        Tip: open this page from your laptop/phone while the Pi runs on the network.<br>
        The robot will only run one motion action at a time.<br>
        If the sentry system is armed, disarm it first before testing motions.
    </div>
</body>
</html>
"""


def run_action(action_name: str):
    global ui_status

    with action_lock:
        if sentry.is_armed():
            set_status("Disarm security mode first")
            return

        set_status(f"Running {action_name}")

        try:
            if action_name == "neutral":
                calibration.move_to_neutral()

            elif action_name == "test_all_servos":
                calibration.test_all_servos()

            else:
                motion_player.play(action_name)

            set_status(f"Finished {action_name}")

        except Exception as exc:
            set_status(f"Error: {exc}")


@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_PAGE, status=get_status())


@app.route("/action/<name>", methods=["POST"])
def action(name):
    valid_actions = {
        "neutral",
        "happy_excited",
        "angry",
        "scared",
        "sad_tired",
        "disgusted",
        "test_all_servos",
    }

    if name not in valid_actions:
        return redirect(url_for("index"))

    thread = threading.Thread(target=run_action, args=(name,), daemon=True)
    thread.start()

    return redirect(url_for("index"))


@app.route("/security/arm", methods=["POST"])
def security_arm():
    if sentry.is_armed():
        set_status("Security already armed")
        return redirect(url_for("index"))

    sentry.arm()
    set_status("Security arming... wait 10 seconds")
    return redirect(url_for("index"))


@app.route("/security/disarm", methods=["POST"])
def security_disarm():
    password = request.form.get("password", "")
    ok = sentry.disarm(password)

    if ok:
        set_status("Security disarmed")
    else:
        set_status("Wrong password")

    return redirect(url_for("index"))


if __name__ == "__main__":
    set_status("Moving robot to neutral on startup...")
    print("Moving robot to neutral on startup...")
    calibration.move_to_neutral()
    set_status("Idle")

    app.run(host="0.0.0.0", port=5000, debug=False)