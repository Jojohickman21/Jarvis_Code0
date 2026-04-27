# calibration.py — INTERACTIVE SERVO CALIBRATION

import time


class CalibrationManager:
    def __init__(self, servo_controller, servo_channels, neutral_angles, offsets, servo_limits=None):
        self.servo_controller = servo_controller
        self.servo_channels = servo_channels
        self.neutral_angles = neutral_angles
        self.offsets = offsets
        self.servo_limits = servo_limits or {}

    # ── CORE HELPERS ───────────────────────────────────────────

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
        print("\n[INFO] Moving to neutral pose...")
        pose = self.get_neutral_pose()
        self.servo_controller.safe_neutral(pose)
        time.sleep(pause)

    # ── MANUAL CALIBRATION MODE ────────────────────────────────

    def manual_calibrate(self):
        print("\n===== SERVO CALIBRATION MODE =====")
        print("Commands:")
        print("  list       → show servos")
        print("  select X   → choose servo")
        print("  angle N    → move to angle")
        print("  center     → go to neutral")
        print("  step +N    → move up")
        print("  step -N    → move down")
        print("  limits     → print limits")
        print("  done       → exit\n")

        current_servo = None
        current_angle = 90

        while True:
            cmd = input(">> ").strip().lower()

            # list servos
            if cmd == "list":
                print(self.servo_channels)

            # select servo
            elif cmd.startswith("select"):
                name = cmd.split(" ")[1]
                if name in self.servo_channels:
                    current_servo = name
                    current_angle = self.neutral_angles[name]
                    print(f"[INFO] Selected: {name}")
                    self.move_servo(name, current_angle)
                else:
                    print("Invalid servo")

            # absolute angle
            elif cmd.startswith("angle"):
                if not current_servo:
                    print("Select a servo first")
                    continue

                try:
                    angle = int(cmd.split(" ")[1])
                    current_angle = angle
                    self.move_servo(current_servo, current_angle)
                except:
                    print("Invalid angle")

            # step movement
            elif cmd.startswith("step"):
                if not current_servo:
                    print("Select a servo first")
                    continue

                try:
                    delta = int(cmd.split(" ")[1])
                    current_angle += delta
                    self.move_servo(current_servo, current_angle)
                except:
                    print("Invalid step")

            # center
            elif cmd == "center":
                if not current_servo:
                    print("Select a servo first")
                    continue

                current_angle = self.neutral_angles[current_servo]
                self.move_servo(current_servo, current_angle)

            # show limits
            elif cmd == "limits":
                print(self.servo_limits)

            # exit
            elif cmd == "done":
                print("\n[INFO] Calibration complete.")
                break

            else:
                print("Unknown command")

    # ── LOW LEVEL MOVE ─────────────────────────────────────────

    def move_servo(self, name, angle):
        channel = self.servo_channels[name]
        angle = self.clamp_angle(name, angle)

        print(f"[MOVE] {name} → {angle}")
        self.servo_controller.set_angle(channel, angle)