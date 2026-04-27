from calibration import CalibrationManager
from config import *
from servo_controller import ServoController  # your existing class

servo_controller = ServoController()

cal = CalibrationManager(
    servo_controller,
    SERVO_CHANNELS,
    NEUTRAL_ANGLES,
    SERVO_OFFSETS,
    SERVO_LIMITS
)

cal.move_to_neutral()
cal.manual_calibrate()